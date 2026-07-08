import re

import pytest
from httpx import ASGITransport, AsyncClient


def _app_with_token(monkeypatch, token="sync-token"):
    from backend.config import get_settings
    from backend.app import create_app

    if token is None:
        monkeypatch.delenv("EDGE_SYNC_TOKEN", raising=False)
    else:
        monkeypatch.setenv("EDGE_SYNC_TOKEN", token)
    get_settings.cache_clear()
    return create_app()


@pytest.mark.asyncio
async def test_edge_config_404_when_token_unset(monkeypatch):
    app = _app_with_token(monkeypatch, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edge-config")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_edge_config_401_on_wrong_token(monkeypatch):
    app = _app_with_token(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edge-config", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_edge_config_exports_endpoint_digests_only(monkeypatch, make_user, make_ingest_endpoint):
    user = make_user()
    ep = make_ingest_endpoint(user["id"])
    app = _app_with_token(monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edge-config", headers={"Authorization": "Bearer sync-token"})
    assert r.status_code == 200
    body = r.json()
    assert re.fullmatch(r"[0-9a-f]{16}", body["version"])
    assert body["ingest_endpoints"] == [
        {"id": str(ep["id"]), "key_sha256": body["ingest_endpoints"][0]["key_sha256"]}
    ]
    assert len(body["ingest_endpoints"][0]["key_sha256"]) == 64
    assert "channels" not in body and "rules" not in body
    assert "token_hash" not in str(body)
