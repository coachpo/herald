"""Test services - channel config normalization."""

import pytest

from ..services import ChannelConfigValidationError
from ..services.channel_validation import _normalize_channel_config


class TestGotifyChannelConfig:
    """Test Gotify channel config validation via _normalize_channel_config."""

    def test_valid_minimal_config(self):
        """Valid minimal config with server_base_url and app_token only."""
        config = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
        }
        result = _normalize_channel_config("gotify", config)

        assert result["server_base_url"] == "https://example.com"
        assert result["app_token"] == "test-token-123"
        assert "default_priority" not in result
        assert "default_extras_json" not in result
        assert "default_payload_json" not in result

    def test_valid_full_config(self):
        """Valid full config with all optional fields."""
        config = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
            "default_priority": 5,
            "default_extras_json": {"key": "value"},
            "default_payload_json": {"custom": "data"},
        }
        result = _normalize_channel_config("gotify", config)

        assert result["server_base_url"] == "https://example.com"
        assert result["app_token"] == "test-token-123"
        assert result["default_priority"] == 5
        assert result["default_extras_json"] == {"key": "value"}
        assert result["default_payload_json"] == {"custom": "data"}

    def test_missing_server_base_url_raises_error(self):
        """Missing server_base_url should raise ChannelConfigValidationError."""
        config = {
            "app_token": "test-token-123",
        }
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            _normalize_channel_config("gotify", config)

        assert "server_base_url" in exc_info.value.details.get("config", {})

    def test_missing_app_token_raises_error(self):
        """Missing app_token should raise ChannelConfigValidationError."""
        config = {
            "server_base_url": "https://example.com",
        }
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            _normalize_channel_config("gotify", config)

        assert "app_token" in exc_info.value.details.get("config", {})

    def test_invalid_priority_negative_raises_error(self):
        """Negative priority should raise ChannelConfigValidationError."""
        config = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
            "default_priority": -1,
        }
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            _normalize_channel_config("gotify", config)

        assert "default_priority" in exc_info.value.details.get("config", {})

    def test_invalid_priority_exceeds_max_raises_error(self):
        """Priority > 10 should raise ChannelConfigValidationError."""
        config = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
            "default_priority": 11,
        }
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            _normalize_channel_config("gotify", config)

        assert "default_priority" in exc_info.value.details.get("config", {})

    def test_invalid_url_scheme_raises_error(self):
        """URL with non-http(s) scheme should raise ChannelConfigValidationError."""
        config = {
            "server_base_url": "ftp://gotify.example.com",
            "app_token": "test-token-123",
        }
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            _normalize_channel_config("gotify", config)

        assert "server_base_url" in exc_info.value.details.get("config", {})

    def test_url_trailing_slash_stripped(self):
        """URL trailing slashes should be stripped."""
        config = {
            "server_base_url": "https://example.com/",
            "app_token": "test-token-123",
        }
        result = _normalize_channel_config("gotify", config)

        assert result["server_base_url"] == "https://example.com"

    def test_priority_boundary_values(self):
        """Priority boundary values 0 and 10 should be valid."""
        config_min = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
            "default_priority": 0,
        }
        result_min = _normalize_channel_config("gotify", config_min)
        assert result_min["default_priority"] == 0

        config_max = {
            "server_base_url": "https://example.com",
            "app_token": "test-token-123",
            "default_priority": 10,
        }
        result_max = _normalize_channel_config("gotify", config_max)
        assert result_max["default_priority"] == 10
