import uuid
from datetime import datetime, timedelta, timezone

import pytest

import backend.worker as worker_mod
from backend.tests.conftest import _run_sql


def _make_delivery(
    make_user,
    make_ingest_endpoint,
    make_channel,
    make_rule,
    *,
    status="queued",
    updated_ago_minutes=0,
    attempts=0,
):
    user = make_user(email=f"{uuid.uuid4().hex[:8]}@x.com")
    ep = make_ingest_endpoint(user["id"])
    ch = make_channel(user["id"])
    rule = make_rule(user["id"], ch["id"])
    now = datetime.now(timezone.utc)
    mid, did = uuid.uuid4(), uuid.uuid4()
    _run_sql(
        "INSERT INTO messages (id, user_id, ingest_endpoint_id, received_at, body, priority, "
        "tags_json, extras_json, body_sha256, headers_json, query_json) "
        "VALUES ($1, $2, $3, $4, 'b', 3, '[]', '{}', 'x', '{}', '{}')",
        mid,
        user["id"],
        ep["id"],
        now,
    )
    _run_sql(
        "INSERT INTO deliveries (id, user_id, message_id, rule_id, channel_id, status, "
        "attempt_count, next_attempt_at, created_at, updated_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, $9)",
        did,
        user["id"],
        mid,
        rule["id"],
        ch["id"],
        status,
        attempts,
        now - timedelta(minutes=updated_ago_minutes),
        now - timedelta(minutes=updated_ago_minutes),
    )
    return did


def test_backoff_series():
    assert [worker_mod._backoff_seconds(n) for n in (1, 2, 3, 10)] == [5, 10, 20, 1800]


@pytest.mark.asyncio
async def test_stale_sending_requeued(make_user, make_ingest_endpoint, make_channel, make_rule):
    did = _make_delivery(
        make_user,
        make_ingest_endpoint,
        make_channel,
        make_rule,
        status="sending",
        updated_ago_minutes=30,
    )
    fresh = _make_delivery(
        make_user,
        make_ingest_endpoint,
        make_channel,
        make_rule,
        status="sending",
        updated_ago_minutes=1,
    )
    from backend.database import get_sessionmaker

    async with get_sessionmaker()() as session:
        swept = await worker_mod._sweep_stale_sending(session, now=datetime.now(timezone.utc))
    assert swept == 1
    assert _run_sql("SELECT status FROM deliveries WHERE id=$1", did)["status"] == "retry"
    assert _run_sql("SELECT status FROM deliveries WHERE id=$1", fresh)["status"] == "sending"


@pytest.mark.asyncio
async def test_batch_success_marks_sent(monkeypatch, make_user, make_ingest_endpoint, make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)

    async def fake_dispatch(**kwargs):
        return True, {"http_status": 200}

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", fake_dispatch)
    claimed = await worker_mod.process_delivery_batch()
    assert claimed == 1
    row = _run_sql("SELECT status, sent_at FROM deliveries WHERE id=$1", did)
    assert row["status"] == "sent" and row["sent_at"] is not None


@pytest.mark.asyncio
async def test_failure_retries_then_fails(monkeypatch, make_user, make_ingest_endpoint, make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule, attempts=9)

    async def fake_dispatch(**kwargs):
        return False, {"http_status": 500}

    monkeypatch.setattr(worker_mod, "dispatch_channel_message", fake_dispatch)
    await worker_mod.process_delivery_batch()
    row = _run_sql("SELECT status, attempt_count FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["attempt_count"] == 10


@pytest.mark.asyncio
async def test_disabled_rule_terminal(monkeypatch, make_user, make_ingest_endpoint, make_channel, make_rule):
    did = _make_delivery(make_user, make_ingest_endpoint, make_channel, make_rule)
    _run_sql("UPDATE rules SET enabled = FALSE")
    await worker_mod.process_delivery_batch()
    row = _run_sql("SELECT status, last_error FROM deliveries WHERE id=$1", did)
    assert row["status"] == "failed" and row["last_error"] == "rule_disabled"
