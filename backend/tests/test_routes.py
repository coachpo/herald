"""Integration tests for FastAPI read-only endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from ..app import create_app


@pytest.fixture
def app():
    """Create FastAPI app."""
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """Test health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

        assert response.status_code in (200, 503)
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert "database" in data
        assert "version" in data
        assert isinstance(data["version"], str)
        assert data["version"]


@pytest.mark.asyncio
async def test_messages_list_requires_auth(app):
    """Test messages list requires authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/messages")

        assert response.status_code == 401  # No auth header


@pytest.mark.asyncio
async def test_channels_list_requires_auth(app):
    """Test channels list requires authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/channels")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_channel_write_routes_require_auth(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        channel_id = "550e8400-e29b-41d4-a716-446655440000"
        body = {
            "type": "bark",
            "name": "Test Channel",
            "config": {
                "server_base_url": "https://1.1.1.1",
                "device_key": "abc1234567890123",
            },
        }

        create_response = await client.post("/api/channels", json=body)
        delete_response = await client.delete(f"/api/channels/{channel_id}")
        test_response = await client.post(
            f"/api/channels/{channel_id}/test",
            json={"body": "hello"},
        )

        assert create_response.status_code == 401
        assert delete_response.status_code == 401
        assert test_response.status_code == 401


@pytest.mark.asyncio
async def test_rules_list_requires_auth(app):
    """Test rules list requires authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/rules")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_rule_write_routes_require_auth(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        rule_id = "550e8400-e29b-41d4-a716-446655440000"
        body = {
            "name": "Test Rule",
            "enabled": True,
            "channel_id": "550e8400-e29b-41d4-a716-446655440001",
            "filter": {"body": {"contains": ["alert"]}},
            "payload_template": {"body": "{{message.body}}"},
        }

        create_response = await client.post("/api/rules", json=body)
        patch_response = await client.patch(f"/api/rules/{rule_id}", json=body)
        delete_response = await client.delete(f"/api/rules/{rule_id}")

        assert create_response.status_code == 401
        assert patch_response.status_code == 401
        assert delete_response.status_code == 401


@pytest.mark.asyncio
async def test_ingest_endpoints_list_requires_auth(app):
    """Test ingest endpoints list requires authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/ingest-endpoints")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_ingest_endpoint_write_routes_require_auth(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        endpoint_id = "550e8400-e29b-41d4-a716-446655440000"

        create_response = await client.post(
            "/api/ingest-endpoints",
            json={"name": "Test Endpoint"},
        )
        patch_response = await client.patch(
            f"/api/ingest-endpoints/{endpoint_id}",
            json={"name": "Renamed Endpoint"},
        )
        delete_response = await client.delete(f"/api/ingest-endpoints/{endpoint_id}")
        revoke_response = await client.post(
            f"/api/ingest-endpoints/{endpoint_id}/revoke"
        )

        assert create_response.status_code == 401
        assert patch_response.status_code == 401
        assert delete_response.status_code == 401
        assert revoke_response.status_code == 401


@pytest.mark.asyncio
async def test_openapi_schema_available(app):
    """Test OpenAPI schema is available."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

        # Check key endpoints are documented
        assert "/health" in schema["paths"]
        assert "/api/messages" in schema["paths"]
        assert "/api/channels" in schema["paths"]
        assert "/api/channels/{channel_id}" in schema["paths"]
        assert "/api/channels/{channel_id}/test" in schema["paths"]
        assert "/api/rules" in schema["paths"]
        assert "/api/rules/{rule_id}" in schema["paths"]
        assert "/api/ingest/{endpoint_id}" in schema["paths"]
        assert "/api/ingest-endpoints" in schema["paths"]
        assert "/api/ingest-endpoints/{endpoint_id}" in schema["paths"]
        assert "/api/ingest-endpoints/{endpoint_id}/revoke" in schema["paths"]


@pytest.mark.asyncio
async def test_response_models_in_schema(app):
    """Test response models are properly defined in schema."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        # Check response schemas exist
        components = schema.get("components", {}).get("schemas", {})

        assert "MessagesResponse" in components
        assert "ChannelsResponse" in components
        assert "ChannelCreateRequest" in components
        assert "ChannelWithConfigResponse" in components
        assert "ChannelTestRequest" in components
        assert "ChannelTestResponse" in components
        assert "RulesResponse" in components
        assert "RuleCreateRequest" in components
        assert "RuleUpdateRequest" in components
        assert "IngestEndpointsResponse" in components
        assert "IngestEndpointCreateRequest" in components
        assert "IngestEndpointCreateResponse" in components
        assert "AuthSessionResponse" in components
        assert "IngestMessageResponse" in components
        assert "MessageSummary" in components
        assert "Channel" in components
        assert "Rule" in components
        assert "IngestEndpoint" in components

        login_response = schema["paths"]["/api/auth/login"]["post"]["responses"]["200"]
        assert login_response["content"]["application/json"]["schema"]["$ref"] == (
            "#/components/schemas/AuthSessionResponse"
        )

        refresh_response = schema["paths"]["/api/auth/refresh"]["post"]["responses"][
            "200"
        ]
        assert refresh_response["content"]["application/json"]["schema"]["$ref"] == (
            "#/components/schemas/AuthSessionResponse"
        )

        ingest_response = schema["paths"]["/api/ingest/{endpoint_id}"]["post"][
            "responses"
        ]["201"]
        assert ingest_response["content"]["application/json"]["schema"]["$ref"] == (
            "#/components/schemas/IngestMessageResponse"
        )


@pytest.mark.asyncio
async def test_message_summary_schema(app):
    """Test MessageSummary schema matches contract."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        message_summary = schema["components"]["schemas"]["MessageSummary"]
        properties = message_summary["properties"]

        # Check required fields from contract
        assert "id" in properties
        assert "ingest_endpoint_id" in properties
        assert "received_at" in properties
        assert "title" in properties
        assert "body_preview" in properties
        assert "group" in properties
        assert "priority" in properties
        assert "tags" in properties
        assert "deliveries" in properties

        # Check deliveries structure
        deliveries_ref = properties["deliveries"]["$ref"]
        assert "DeliveryCounters" in deliveries_ref


@pytest.mark.asyncio
async def test_channel_schema(app):
    """Test Channel schema matches contract."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        channel = schema["components"]["schemas"]["Channel"]
        properties = channel["properties"]

        # Check required fields from contract
        assert "id" in properties
        assert "type" in properties
        assert "name" in properties
        assert "created_at" in properties
        assert "disabled_at" in properties


@pytest.mark.asyncio
async def test_rule_schema(app):
    """Test Rule schema matches contract."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        rule = schema["components"]["schemas"]["Rule"]
        properties = rule["properties"]

        # Check required fields from contract
        assert "id" in properties
        assert "name" in properties
        assert "enabled" in properties
        assert "channel_id" in properties
        assert "filter" in properties
        assert "payload_template" in properties
        assert "created_at" in properties
        assert "updated_at" in properties


@pytest.mark.asyncio
async def test_rule_write_request_schemas(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        create_request = schema["components"]["schemas"]["RuleCreateRequest"]
        update_request = schema["components"]["schemas"]["RuleUpdateRequest"]

        assert set(create_request["required"]) == {"name", "enabled", "channel_id"}
        assert set(update_request["required"]) == {"name", "enabled", "channel_id"}
        assert create_request["properties"]["name"]["maxLength"] == 200
        assert update_request["properties"]["name"]["maxLength"] == 200
        assert "filter" in create_request["properties"]
        assert "payload_template" in create_request["properties"]
        assert "filter" in update_request["properties"]
        assert "payload_template" in update_request["properties"]


@pytest.mark.asyncio
async def test_ingest_endpoint_schema(app):
    """Test IngestEndpoint schema matches contract."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        endpoint = schema["components"]["schemas"]["IngestEndpoint"]
        properties = endpoint["properties"]

        # Check required fields from contract
        assert "id" in properties
        assert "name" in properties
        assert "created_at" in properties
        assert "last_used_at" in properties
        assert "revoked_at" in properties


@pytest.mark.asyncio
async def test_ingest_endpoint_create_schema(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/openapi.json")
        schema = response.json()

        create_request = schema["components"]["schemas"]["IngestEndpointCreateRequest"]
        create_response = schema["components"]["schemas"][
            "IngestEndpointCreateResponse"
        ]

        assert create_request["required"] == ["name"]
        assert "name" in create_request["properties"]
        assert set(create_response["required"]) == {
            "endpoint",
            "ingest_key",
            "ingest_url",
        }
