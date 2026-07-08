import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.tests.conftest import _run_sql

PUBLIC_IP_URL = "https://93.184.216.34"


async def _authed_client(app):
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    email = f"{uuid.uuid4().hex[:8]}@x.com"
    await client.post("/api/auth/signup", json={"email": email, "password": "pw-123456"})
    login = (
        await client.post(
            "/api/auth/login",
            json={"email": email, "password": "pw-123456"},
        )
    ).json()
    client.headers["Authorization"] = f"Bearer {login['access_token']}"
    return client


async def _create_channel(client, name):
    response = await client.post(
        "/api/channels",
        json={
            "type": "ntfy",
            "name": name,
            "config": {"server_base_url": PUBLIC_IP_URL, "topic": "t"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["channel"]["id"]


@pytest.mark.asyncio
async def test_channel_create_and_list_roundtrip(app):
    client = await _authed_client(app)
    try:
        await _create_channel(client, "ch1")
        listed = (await client.get("/api/channels")).json()
        assert any(ch["name"] == "ch1" for ch in listed["channels"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_rule_create(app):
    client = await _authed_client(app)
    try:
        channel_id = await _create_channel(client, "ch2")
        response = await client.post(
            "/api/rules",
            json={
                "name": "r1",
                "enabled": True,
                "channel_id": channel_id,
                "filter": {},
                "payload_template": {},
            },
        )
        assert response.status_code == 201, response.text
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_ingest_endpoint_create_then_revoke_blocks_ingest(app):
    client = await _authed_client(app)
    try:
        created = (
            await client.post("/api/ingest-endpoints", json={"name": "ep1"})
        ).json()
        key = created["ingest_key"]
        endpoint_id = created["endpoint"]["id"]
        ok = await client.post(
            f"/api/ingest/{endpoint_id}",
            json={"body": "hi"},
            headers={"X-Herald-Ingest-Key": key},
        )
        assert ok.status_code == 201
        revoked = await client.post(f"/api/ingest-endpoints/{endpoint_id}/revoke")
        assert revoked.status_code == 204, revoked.text
        blocked = await client.post(
            f"/api/ingest/{endpoint_id}",
            json={"body": "hi"},
            headers={"X-Herald-Ingest-Key": key},
        )
        assert blocked.status_code == 401
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_messages_list_shows_ingested_message_with_deliveries(app):
    client = await _authed_client(app)
    try:
        channel_id = await _create_channel(client, "ch3")
        await client.post(
            "/api/rules",
            json={
                "name": "r2",
                "enabled": True,
                "channel_id": channel_id,
                "filter": {},
                "payload_template": {},
            },
        )
        created = (
            await client.post("/api/ingest-endpoints", json={"name": "ep2"})
        ).json()
        sent = await client.post(
            f"/api/ingest/{created['endpoint']['id']}",
            json={"body": "hello world"},
            headers={"X-Herald-Ingest-Key": created["ingest_key"]},
        )
        assert sent.status_code == 201
        message_id = sent.json()["message_id"]
        listed = (await client.get("/api/messages")).json()
        message = next(
            m for m in listed["messages"] if m["id"] == message_id
        )
        assert message["body_preview"] == "hello world"
        assert message["deliveries"]["queued"] == 1
        assert _run_sql("SELECT count(*) AS n FROM deliveries")["n"] == 1
    finally:
        await client.aclose()
