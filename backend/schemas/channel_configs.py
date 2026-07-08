"""Channel config validation as Pydantic models."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..core.ssrf import assert_host_ssrf_safe, assert_ssrf_safe
from ..services.exceptions import ChannelConfigValidationError

CHANNEL_TYPE_BARK = "bark"
CHANNEL_TYPE_NTFY = "ntfy"
CHANNEL_TYPE_MQTT = "mqtt"
CHANNEL_TYPE_GOTIFY = "gotify"
SUPPORTED_CHANNEL_TYPES = (
    CHANNEL_TYPE_BARK,
    CHANNEL_TYPE_NTFY,
    CHANNEL_TYPE_MQTT,
    CHANNEL_TYPE_GOTIFY,
)


def _looks_like_device_key(segment: str) -> bool:
    return (
        len(segment) >= 16
        and any(ch.isdigit() for ch in segment)
        and all(ch.isalnum() or ch in "_-" for ch in segment)
    )


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BarkConfig(_Config):
    server_base_url: str
    device_key: str | None = None
    device_keys: list[str] | None = None
    default_payload_json: dict | None = None

    @model_validator(mode="after")
    def _normalize(self) -> "BarkConfig":
        base = self.server_base_url.rstrip("/")
        if base.endswith("/push"):
            base = base[: -len("/push")].rstrip("/")
        if not self.device_key and not self.device_keys:
            parsed = urlparse(base)
            segments = [s for s in parsed.path.split("/") if s]
            if len(segments) == 1 and _looks_like_device_key(segments[0]):
                self.device_key = segments[0]
                base = f"{parsed.scheme}://{parsed.netloc}"
            else:
                raise ValueError("device_key is required (or set device_keys)")
        self.server_base_url = base
        assert_ssrf_safe(base)
        return self


class NtfyConfig(_Config):
    server_base_url: str
    topic: str
    access_token: str | None = None
    username: str | None = None
    password: str | None = None
    default_headers_json: dict | None = None

    @model_validator(mode="after")
    def _check_auth(self) -> "NtfyConfig":
        if self.access_token and (self.username or self.password):
            raise ValueError("choose one auth method: access_token or username/password")
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be set together")
        self.server_base_url = self.server_base_url.rstrip("/")
        assert_ssrf_safe(f"{self.server_base_url}/{self.topic}")
        return self


class MqttConfig(_Config):
    broker_host: str
    topic: str
    broker_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    tls: bool | None = None
    tls_insecure: bool | None = None
    qos: int | None = Field(default=None, ge=0, le=2)
    retain: bool | None = None
    client_id: str | None = None
    keepalive_seconds: int | None = Field(default=None, ge=1, le=3600)

    @model_validator(mode="after")
    def _check(self) -> "MqttConfig":
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be set together")
        assert_host_ssrf_safe(self.broker_host, block_private_networks=True)
        return self


class GotifyConfig(_Config):
    server_base_url: str
    app_token: str
    default_priority: int | None = Field(default=None, ge=0, le=10)
    default_extras_json: dict | None = None
    default_payload_json: dict | None = None

    @model_validator(mode="after")
    def _check_url(self) -> "GotifyConfig":
        parsed = urlparse(self.server_base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("server_base_url must be an http(s) URL")
        self.server_base_url = self.server_base_url.rstrip("/")
        assert_ssrf_safe(self.server_base_url)
        return self


_MODELS: dict[str, type[_Config]] = {
    CHANNEL_TYPE_BARK: BarkConfig,
    CHANNEL_TYPE_NTFY: NtfyConfig,
    CHANNEL_TYPE_MQTT: MqttConfig,
    CHANNEL_TYPE_GOTIFY: GotifyConfig,
}


def normalize_channel_type(raw: object) -> str:
    value = str(raw or "").strip()
    if value not in _MODELS:
        raise ChannelConfigValidationError(details={"type": [f'"{value}" is not a valid choice.']})
    return value


def normalize_channel_config(channel_type: str, config: object) -> dict:
    if not isinstance(config, dict):
        raise ChannelConfigValidationError(
            details={"config": {"non_field_errors": ["Expected an object."]}}
        )
    model = _MODELS[normalize_channel_type(channel_type)]
    try:
        validated = model.model_validate(config)
    except ValidationError as exc:
        details: dict[str, list[str]] = {}
        for err in exc.errors():
            field = str(err["loc"][0]) if err["loc"] else "non_field_errors"
            details.setdefault(field, []).append(
                str(err["msg"]).removeprefix("Value error, ")
            )
        raise ChannelConfigValidationError(details={"config": details}) from exc
    return validated.model_dump(exclude_none=True)
