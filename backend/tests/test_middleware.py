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
async def test_health_not_access_logged(app, capsys):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.get("/health")

    capsys.readouterr()
