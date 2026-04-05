from __future__ import annotations

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from ..app import create_app


class ValidationPayload(BaseModel):
    name: str
    enabled: bool


@pytest.fixture
def app():
    app = create_app()

    @app.get("/test-http-exception")
    async def http_exception_route() -> None:
        raise HTTPException(status_code=404, detail="not_found")

    @app.post("/test-validation-error")
    async def validation_route(payload: ValidationPayload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/test-unhandled-exception")
    async def unhandled_exception_route() -> None:
        raise RuntimeError("boom")

    return app


@pytest.mark.asyncio
async def test_http_exception_returns_consistent_envelope(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/test-http-exception")

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


@pytest.mark.asyncio
async def test_validation_error_returns_field_errors(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/test-validation-error", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "validation_error"
    assert {(item["field"], item["message"]) for item in response.json()["errors"]} == {
        ("body.name", "Field required"),
        ("body.enabled", "Field required"),
    }


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(app):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/test-unhandled-exception")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal_server_error"}
    assert "RuntimeError" not in response.text
    assert "boom" not in response.text
