import pytest
from httpx import ASGITransport, AsyncClient


async def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_signup_login_me_roundtrip(app):
    async with await _client(app) as c:
        r = await c.post(
            "/api/auth/signup", json={"email": "a@x.com", "password": "pw-123456"}
        )
        assert r.status_code == 201
        r = await c.post(
            "/api/auth/login", json={"email": "a@x.com", "password": "pw-123456"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"] and body["refresh_token"]
        r = await c.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "a@x.com"
        assert "email_verified_at" not in r.json()["user"]


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(app):
    async with await _client(app) as c:
        await c.post(
            "/api/auth/signup", json={"email": "b@x.com", "password": "pw-123456"}
        )
        login = (
            await c.post(
                "/api/auth/login",
                json={"email": "b@x.com", "password": "pw-123456"},
            )
        ).json()
        old_refresh = login["refresh_token"]
        r1 = await c.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r1.status_code == 200
        new_refresh = r1.json()["refresh_token"]
        assert new_refresh != old_refresh
        r2 = await c.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401
        r3 = await c.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert r3.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh(app):
    async with await _client(app) as c:
        await c.post(
            "/api/auth/signup", json={"email": "c@x.com", "password": "pw-123456"}
        )
        login = (
            await c.post(
                "/api/auth/login",
                json={"email": "c@x.com", "password": "pw-123456"},
            )
        ).json()
        r = await c.post(
            "/api/auth/logout",
            json={"refresh_token": login["refresh_token"]},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert r.status_code == 204
        r = await c.post(
            "/api/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_all_sessions(app):
    async with await _client(app) as c:
        await c.post(
            "/api/auth/signup", json={"email": "d@x.com", "password": "pw-123456"}
        )
        login = (
            await c.post(
                "/api/auth/login",
                json={"email": "d@x.com", "password": "pw-123456"},
            )
        ).json()
        r = await c.post(
            "/api/auth/change-password",
            json={"old_password": "pw-123456", "new_password": "pw-654321"},
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert r.status_code == 204
        r = await c.post(
            "/api/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_dead_mailer_endpoints_are_gone(app):
    async with await _client(app) as c:
        for path in (
            "/api/auth/verify-email",
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
            "/api/auth/resend-verification",
        ):
            r = await c.post(path, json={})
            assert r.status_code == 404, path
