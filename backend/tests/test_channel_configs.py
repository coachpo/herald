import socket

import pytest

from backend.schemas.channel_configs import normalize_channel_config
from backend.services.exceptions import ChannelConfigValidationError


@pytest.fixture(autouse=True)
def _dns(monkeypatch):
    def fake_getaddrinfo(host, *args, **kwargs):
        if host in {"192.168.1.10", "127.0.0.1", "localhost"}:
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


class TestGotifyChannelConfig:
    def test_valid_minimal_config(self):
        result = normalize_channel_config(
            "gotify",
            {"server_base_url": "https://example.com", "app_token": "test-token-123"},
        )

        assert result["server_base_url"] == "https://example.com"
        assert result["app_token"] == "test-token-123"
        assert "default_priority" not in result

    def test_valid_full_config(self):
        result = normalize_channel_config(
            "gotify",
            {
                "server_base_url": "https://example.com",
                "app_token": "test-token-123",
                "default_priority": 5,
                "default_extras_json": {"key": "value"},
                "default_payload_json": {"custom": "data"},
            },
        )

        assert result["default_priority"] == 5
        assert result["default_extras_json"] == {"key": "value"}
        assert result["default_payload_json"] == {"custom": "data"}

    @pytest.mark.parametrize(
        "config,field",
        [
            ({"app_token": "x"}, "server_base_url"),
            ({"server_base_url": "https://example.com"}, "app_token"),
            (
                {
                    "server_base_url": "https://example.com",
                    "app_token": "x",
                    "default_priority": -1,
                },
                "default_priority",
            ),
            (
                {
                    "server_base_url": "https://example.com",
                    "app_token": "x",
                    "default_priority": 11,
                },
                "default_priority",
            ),
        ],
    )
    def test_field_errors(self, config, field):
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            normalize_channel_config("gotify", config)

        assert field in exc_info.value.details.get("config", {})

    def test_invalid_url_scheme_raises_error(self):
        with pytest.raises(ChannelConfigValidationError) as exc_info:
            normalize_channel_config(
                "gotify",
                {"server_base_url": "ftp://gotify.example.com", "app_token": "x"},
            )

        assert "non_field_errors" in exc_info.value.details.get("config", {})

    def test_url_trailing_slash_stripped(self):
        result = normalize_channel_config(
            "gotify",
            {"server_base_url": "https://example.com/", "app_token": "x"},
        )

        assert result["server_base_url"] == "https://example.com"

    def test_priority_boundary_values(self):
        assert (
            normalize_channel_config(
                "gotify",
                {
                    "server_base_url": "https://example.com",
                    "app_token": "x",
                    "default_priority": 0,
                },
            )["default_priority"]
            == 0
        )
        assert (
            normalize_channel_config(
                "gotify",
                {
                    "server_base_url": "https://example.com",
                    "app_token": "x",
                    "default_priority": 10,
                },
            )["default_priority"]
            == 10
        )


def test_bark_extracts_device_key_from_url():
    result = normalize_channel_config(
        "bark", {"server_base_url": "https://bark.example.com/abcdefghijklmnop1"}
    )

    assert result["server_base_url"] == "https://bark.example.com"
    assert result["device_key"] == "abcdefghijklmnop1"


def test_bark_requires_device_key():
    with pytest.raises(ChannelConfigValidationError) as exc_info:
        normalize_channel_config("bark", {"server_base_url": "https://bark.example.com"})

    assert "non_field_errors" in exc_info.value.details["config"]


def test_ntfy_rejects_double_auth():
    with pytest.raises(ChannelConfigValidationError) as exc_info:
        normalize_channel_config(
            "ntfy",
            {
                "server_base_url": "https://ntfy.example.com",
                "topic": "t",
                "access_token": "token",
                "username": "u",
                "password": "p",
            },
        )

    assert "non_field_errors" in exc_info.value.details["config"]


def test_mqtt_rejects_private_host():
    with pytest.raises(ChannelConfigValidationError):
        normalize_channel_config(
            "mqtt",
            {"broker_host": "192.168.1.10", "topic": "t"},
        )
