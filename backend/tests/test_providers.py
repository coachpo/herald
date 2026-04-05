"""Test provider modules."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.providers.bark import build_bark_payload, build_push_url
from backend.providers.gotify import build_gotify_payload, send_gotify_push
from backend.providers.ntfy import (
    build_ntfy_request,
    build_topic_url,
    _coerce_header_value,
)


class TestBark:
    """Test Bark provider."""

    def test_build_push_url(self):
        """Build push URL from server base."""
        assert build_push_url("https://api.day.app") == "https://api.day.app/push"
        assert build_push_url("https://api.day.app/") == "https://api.day.app/push"
        assert build_push_url("https://api.day.app/push") == "https://api.day.app/push"

    def test_build_bark_payload(self):
        """Build Bark payload from config and message."""
        channel_config = {
            "device_key": "test-device-key",
            "default_payload_json": {"sound": "bell"},
        }
        payload_template = {"body": "{{message.body}}", "title": "{{message.title}}"}
        message = {"body": "test body", "title": "test title", "priority": 3}
        endpoint = {"name": "test-endpoint"}

        payload = build_bark_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["body"] == "test body"
        assert payload["title"] == "test title"
        assert payload["device_key"] == "test-device-key"
        assert payload["sound"] == "bell"

    def test_build_bark_payload_with_device_keys(self):
        """Build Bark payload with multiple device keys."""
        channel_config = {
            "device_keys": ["key1", "key2"],
        }
        payload_template = {}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_bark_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["device_keys"] == ["key1", "key2"]


class TestNtfy:
    """Test ntfy provider."""

    def test_build_topic_url(self):
        """Build topic URL from server and topic."""
        assert (
            build_topic_url("https://ntfy.sh", "mytopic") == "https://ntfy.sh/mytopic"
        )
        assert (
            build_topic_url("https://ntfy.sh/", "mytopic") == "https://ntfy.sh/mytopic"
        )
        assert (
            build_topic_url("https://ntfy.sh", "/mytopic") == "https://ntfy.sh/mytopic"
        )

    def test_coerce_header_value(self):
        """Coerce various types to header strings."""
        assert _coerce_header_value(None) is None
        assert _coerce_header_value(True) == "true"
        assert _coerce_header_value(False) == "false"
        assert _coerce_header_value(42) == "42"
        assert _coerce_header_value(3.14) == "3.14"
        assert _coerce_header_value("test") == "test"
        assert _coerce_header_value("  ") is None  # Empty after strip

    def test_build_ntfy_request_basic(self):
        """Build basic ntfy request."""
        channel_config = {
            "server_base_url": "https://ntfy.sh",
            "topic": "test-topic",
        }
        payload_template = {"body": "{{message.body}}"}
        message = {"body": "test message", "title": "test title", "priority": 3}
        endpoint = {"name": "test"}

        url, body, headers, auth = build_ntfy_request(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
            block_private_networks=False,
        )

        assert url == "https://ntfy.sh/test-topic"
        assert body == b"test message"
        assert headers["Title"] == "test title"
        assert auth is None

    def test_build_ntfy_request_with_auth(self):
        """Build ntfy request with authentication."""
        channel_config = {
            "server_base_url": "https://ntfy.sh",
            "topic": "test-topic",
            "username": "user",
            "password": "pass",
        }
        payload_template = {}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        url, body, headers, auth = build_ntfy_request(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
            block_private_networks=False,
        )

        assert auth == ("user", "pass")

    def test_build_ntfy_request_with_token(self):
        """Build ntfy request with bearer token."""
        channel_config = {
            "server_base_url": "https://ntfy.sh",
            "topic": "test-topic",
            "access_token": "secret-token",
        }
        payload_template = {}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        url, body, headers, auth = build_ntfy_request(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
            block_private_networks=False,
        )

        assert headers["Authorization"] == "Bearer secret-token"
        assert auth is None  # Token takes precedence

    def test_build_ntfy_request_priority_mapping(self):
        """Test priority mapping to ntfy format."""
        channel_config = {
            "server_base_url": "https://ntfy.sh",
            "topic": "test",
        }
        payload_template = {}
        endpoint = {"name": "test"}

        # Test priority 5 -> urgent
        message = {"body": "test", "priority": 5}
        _, _, headers, _ = build_ntfy_request(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
            block_private_networks=False,
        )
        assert headers["Priority"] == "urgent"

        # Test priority 1 -> min
        message = {"body": "test", "priority": 1}
        _, _, headers, _ = build_ntfy_request(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
            block_private_networks=False,
        )
        assert headers["Priority"] == "min"

    def test_build_ntfy_request_missing_config(self):
        """Missing required config should raise ValueError."""
        with pytest.raises(ValueError, match="missing_server_base_url"):
            build_ntfy_request(
                channel_config={"topic": "test"},
                payload_template={},
                message={"body": "test", "priority": 3},
                ingest_endpoint={"name": "test"},
                block_private_networks=False,
            )

        with pytest.raises(ValueError, match="missing_topic"):
            build_ntfy_request(
                channel_config={"server_base_url": "https://ntfy.sh"},
                payload_template={},
                message={"body": "test", "priority": 3},
                ingest_endpoint={"name": "test"},
                block_private_networks=False,
            )


class TestGotify:
    """Test Gotify provider."""

    def test_build_gotify_payload_basic(self):
        """Build basic Gotify payload with body and title."""
        channel_config = {}
        payload_template = {"body": "{{message.body}}", "title": "{{message.title}}"}
        message = {"body": "test body", "title": "test title", "priority": 3}
        endpoint = {"name": "test-endpoint"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["message"] == "test body"
        assert payload["title"] == "test title"

    def test_build_gotify_payload_priority_mapping(self):
        """Test priority mapping: 1→0, 2→2, 4→7, 5→10."""
        channel_config = {}
        payload_template = {}
        endpoint = {"name": "test"}

        # Priority 1 → 0
        message = {"body": "test", "priority": 1}
        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )
        assert payload["priority"] == 0

        # Priority 2 → 2
        message = {"body": "test", "priority": 2}
        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )
        assert payload["priority"] == 2

        # Priority 4 → 7
        message = {"body": "test", "priority": 4}
        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )
        assert payload["priority"] == 7

        # Priority 5 → 10
        message = {"body": "test", "priority": 5}
        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )
        assert payload["priority"] == 10

    def test_build_gotify_payload_default_extras(self):
        """Test default_extras_json merges into extras."""
        channel_config = {"default_extras_json": {"custom_key": "custom_value"}}
        payload_template = {"extras": {"template_key": "template_value"}}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["extras"]["custom_key"] == "custom_value"
        assert payload["extras"]["template_key"] == "template_value"

    def test_build_gotify_payload_markdown_flag(self):
        """Test markdown=True sets client::display contentType."""
        channel_config = {}
        payload_template = {"markdown": True}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["extras"]["client::display"]["contentType"] == "text/markdown"

    def test_build_gotify_payload_click_url(self):
        """Test click URL in template sets client::notification."""
        channel_config = {}
        payload_template = {"click": "https://example.com"}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert (
            payload["extras"]["client::notification"]["click"]["url"]
            == "https://example.com"
        )

    def test_build_gotify_payload_default_priority(self):
        """Test default_priority from config used when message priority is 3."""
        channel_config = {"default_priority": 7}
        payload_template = {}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["priority"] == 7

    def test_build_gotify_payload_default_payload_merge(self):
        """Test default_payload_json merges as base."""
        channel_config = {"default_payload_json": {"sound": "bell", "vibration": True}}
        payload_template = {"body": "test message"}
        message = {"body": "test", "priority": 3}
        endpoint = {"name": "test"}

        payload = build_gotify_payload(
            channel_config=channel_config,
            payload_template=payload_template,
            message=message,
            ingest_endpoint=endpoint,
        )

        assert payload["sound"] == "bell"
        assert payload["vibration"] is True
        assert payload["message"] == "test message"

    @pytest.mark.asyncio
    async def test_send_gotify_push_url_and_headers(self):
        """Test send_gotify_push constructs correct URL and headers."""
        with (
            patch("backend.providers.gotify.assert_ssrf_safe") as mock_ssrf,
            patch(
                "backend.providers.gotify.httpx.AsyncClient"
            ) as mock_client_class,
        ):
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.content = b'{"id": 1}'
            # json() is synchronous in httpx.Response
            mock_response.json = lambda: {"id": 1}

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            ok, meta = await send_gotify_push(
                server_base_url="https://gotify.example.com",
                app_token="test-token",
                payload={"message": "test"},
                timeout=5.0,
                block_private_networks=False,
            )

            assert ok is True
            assert meta["http_status"] == 200
            assert meta["json"] == {"id": 1}

            # Verify URL and headers
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["json"] == {"message": "test"}
            assert call_args[1]["headers"]["X-Gotify-Key"] == "test-token"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"
            assert "https://gotify.example.com/message" in call_args[0]
