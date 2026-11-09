"""Small explicit configurations; credentials are encrypted by the store."""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .core.ssrf import assert_host_ssrf_safe, assert_ssrf_safe

class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

def _base_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.query or parts.fragment or parts.username is not None or parts.password is not None:
        raise ValueError("server URL must not contain credentials, query, or fragment")
    assert_ssrf_safe(value)
    return value.rstrip("/")

class BarkConfig(_Config):
    server_base_url: str
    device_key: str = Field(min_length=1)
    @model_validator(mode="after")
    def check(self):
        self.server_base_url = _base_url(self.server_base_url)
        return self

class NtfyConfig(_Config):
    server_base_url: str
    topic: str = Field(min_length=1)
    access_token: str | None = None
    @model_validator(mode="after")
    def check(self):
        self.server_base_url = _base_url(self.server_base_url)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.topic):
            raise ValueError("topic must contain only letters, digits, _ or -")
        if self.access_token and any(c in self.access_token for c in "\r\n"):
            raise ValueError("invalid access token")
        return self

class GotifyConfig(_Config):
    server_base_url: str
    app_token: str = Field(min_length=1)
    @model_validator(mode="after")
    def check(self):
        self.server_base_url = _base_url(self.server_base_url)
        if any(c in self.app_token for c in "\r\n"):
            raise ValueError("invalid application token")
        return self

class MqttConfig(_Config):
    broker_host: str = Field(min_length=1)
    broker_port: int = Field(default=1883, ge=1, le=65535)
    topic: str = Field(min_length=1)
    username: str | None = None
    password: str | None = None
    tls: bool = False
    qos: int = Field(default=1, ge=0, le=2)
    retain: bool = False
    @model_validator(mode="after")
    def check(self):
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be provided together")
        if any(c in self.topic for c in ("#", "+", "\0")):
            raise ValueError("publish topic must not contain wildcards or NUL")
        assert_host_ssrf_safe(self.broker_host, block_private_networks=True)
        return self

_MODELS = {"bark": BarkConfig, "ntfy": NtfyConfig, "mqtt": MqttConfig, "gotify": GotifyConfig}

def normalize_target_config(kind: str, config: dict) -> dict:
    model = _MODELS.get(kind)
    if model is None:
        raise ValueError("unsupported_target")
    return model.model_validate(config).model_dump(exclude_none=True)
