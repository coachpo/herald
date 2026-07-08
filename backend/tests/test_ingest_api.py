import uuid

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def setup(make_user, make_ingest_endpoint):
    user = make_user()
    ep = make_ingest_endpoint(user["id"])
    return user, ep


def _url(ep):
    return f"/api/ingest/{ep['id'].hex}"


async def _post(app, ep, json_body=None, headers=None, raw=None):
    h = {"X-Herald-Ingest-Key": ep["raw_key"], "Content-Type": "application/json"}
    h.update(headers or {})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        if raw is not None:
            return await c.post(_url(ep), content=raw, headers=h)
        return await c.post(_url(ep), json=json_body, headers=h)


@pytest.mark.asyncio
async def test_wrong_key_401(app, setup):
    _, ep = setup
    r = await _post(app, {**ep, "raw_key": "wrong"}, {"body": "hi"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_happy_path_201_creates_delivery(app, setup, make_channel, make_rule):
    user, ep = setup
    ch = make_channel(user["id"])
    make_rule(user["id"], ch["id"])
    r = await _post(app, ep, {"body": "hello", "priority": 5})
    assert r.status_code == 201
    mid = r.json()["message_id"]
    from backend.tests.conftest import _run_sql

    row = _run_sql("SELECT count(*) AS n FROM deliveries WHERE message_id = $1", uuid.UUID(mid))
    assert row["n"] == 1


@pytest.mark.asyncio
async def test_validation_errors(app, setup):
    _, ep = setup
    assert (await _post(app, ep, {"body": "x", "bogus": 1})).status_code == 422
    assert (await _post(app, ep, {"title": "no body"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "javascript://example.com/%0aalert(1)"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "ftp://example.com/x"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "http:///x"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "http://:80/x"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "http://user@:80/x"})).status_code == 422
    assert (await _post(app, ep, {"body": "x", "url": "http://example.com:bad/x"})).status_code == 422
    assert (await _post(app, ep, raw=b"not json")).status_code == 400
    assert (await _post(app, ep, raw=b"x" * (1024 * 1024 + 1))).status_code == 413
    r = await _post(app, ep, raw=b"plain", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_ingest_rate_limit_429(setup, monkeypatch):
    _, ep = setup
    monkeypatch.setenv("RATE_LIMIT_INGEST_PER_MINUTE", "2")
    from backend.config import get_settings
    from backend.app import create_app

    get_settings.cache_clear()
    app = create_app()
    statuses = [(await _post(app, ep, {"body": "x"})).status_code for _ in range(4)]
    assert statuses[0] in (201, 200) and 429 in statuses


@pytest.mark.asyncio
async def test_relay_idempotency(app, setup, make_channel, make_rule):
    user, ep = setup
    ch = make_channel(user["id"])
    make_rule(user["id"], ch["id"])
    mid = str(uuid.uuid4())
    relay = {"X-Herald-Message-Id": mid, "X-Herald-Relay-Via": "edgeone,cloudflare"}
    r1 = await _post(app, ep, {"body": "once"}, headers=relay)
    assert r1.status_code == 201
    assert r1.json()["message_id"].replace("-", "") == mid.replace("-", "")
    r2 = await _post(app, ep, {"body": "once"}, headers=relay)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is True
    from backend.tests.conftest import _run_sql

    assert _run_sql("SELECT count(*) AS n FROM messages")["n"] == 1
    assert _run_sql("SELECT count(*) AS n FROM deliveries")["n"] == 1
    assert _run_sql("SELECT relay_via FROM messages LIMIT 1")["relay_via"] == "edgeone,cloudflare"


@pytest.mark.asyncio
async def test_bad_relay_message_id_422(app, setup):
    _, ep = setup
    r = await _post(app, ep, {"body": "x"}, headers={"X-Herald-Message-Id": "not-a-uuid"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_revoked_endpoint_401(app, setup):
    _, ep = setup
    from backend.tests.conftest import _run_sql

    _run_sql("UPDATE ingest_endpoints SET revoked_at = now() WHERE id = $1", ep["id"])
    r = await _post(app, ep, {"body": "x"})
    assert r.status_code == 401
