import uuid as _uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_request_id_generated_when_missing(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code in (200, 503)
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) == 32


@pytest.mark.asyncio
async def test_request_id_echoed_when_provided(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health", headers={"X-Request-ID": "test-rid-123"})

    assert response.headers.get("X-Request-ID") == "test-rid-123"


@pytest.mark.asyncio
async def test_auth_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    from backend.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        statuses = []
        for _ in range(5):
            r = await c.post(
                "/api/auth/login", json={"email": "x@x.com", "password": "wrong"}
            )
            statuses.append(r.status_code)
    assert 429 in statuses
    assert statuses[0] != 429


def _fresh_app(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from backend.config import get_settings

    get_settings.cache_clear()
    return create_app()


@pytest.mark.asyncio
async def test_ingest_rate_limit_bucket_is_canonical(monkeypatch):
    app = _fresh_app(monkeypatch, RATE_LIMIT_INGEST_PER_MINUTE="2")
    eid = _uuid.uuid4()
    forms = [str(eid), eid.hex, str(eid).upper()]
    statuses = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for form in forms:
            r = await c.post(
                f"/api/ingest/{form}",
                json={"body": "x"},
                headers={"X-Herald-Ingest-Key": "bogus"},
            )
            statuses.append(r.status_code)
    assert statuses == [401, 401, 429]


@pytest.mark.asyncio
async def test_ingest_rate_limit_differs_per_endpoint(monkeypatch):
    app = _fresh_app(monkeypatch, RATE_LIMIT_INGEST_PER_MINUTE="1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post(
            f"/api/ingest/{_uuid.uuid4()}",
            json={"body": "x"},
            headers={"X-Herald-Ingest-Key": "bogus"},
        )
        r2 = await c.post(
            f"/api/ingest/{_uuid.uuid4()}",
            json={"body": "x"},
            headers={"X-Herald-Ingest-Key": "bogus"},
        )
    assert (r1.status_code, r2.status_code) == (401, 401)


def test_rate_limit_bounded_under_fresh_key_flood():
    """Garbage-key floods must not grow the bucket table without bound."""
    from backend.middleware import RateLimitMiddleware

    mw = RateLimitMiddleware(app=None)
    for i in range(20_000):
        assert mw._allow(f"ingest:1.2.3.4:garbage-{i}", 120) is True

    assert len(mw._buckets) <= 10_000
