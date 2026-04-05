from __future__ import annotations

from typing import Any

from ..core.ssrf import assert_host_ssrf_safe, assert_ssrf_safe
from ..providers.ntfy import build_topic_url
from .exceptions import ChannelConfigValidationError

CHANNEL_TYPE_BARK = "bark"
CHANNEL_TYPE_NTFY = "ntfy"
CHANNEL_TYPE_MQTT = "mqtt"
CHANNEL_TYPE_GOTIFY = "gotify"
SUPPORTED_CHANNEL_TYPES = {
    CHANNEL_TYPE_BARK,
    CHANNEL_TYPE_NTFY,
    CHANNEL_TYPE_MQTT,
    CHANNEL_TYPE_GOTIFY,
}
_MISSING = object()


def field_error(
    field: str,
    message: str,
    *,
    in_config: bool = False,
) -> ChannelConfigValidationError:
    if in_config:
        return ChannelConfigValidationError({"config": {field: [message]}})
    return ChannelConfigValidationError({field: [message]})


def config_non_field_error(message: str) -> ChannelConfigValidationError:
    return ChannelConfigValidationError({"config": {"non_field_errors": [message]}})


def require_string_field(
    data: dict[str, Any],
    field: str,
    *,
    in_config: bool = False,
) -> str:
    if field not in data:
        raise field_error(field, "This field is required.", in_config=in_config)

    value = str(data.get(field) or "").strip()
    if not value:
        raise field_error(field, "This field may not be blank.", in_config=in_config)
    return value


def optional_string_field(data: dict[str, Any], field: str) -> str | None | object:
    if field not in data:
        return _MISSING
    raw = data.get(field)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def optional_dict_field(data: dict[str, Any], field: str) -> dict[str, Any] | object:
    if field not in data:
        return _MISSING
    value = data.get(field)
    if value is None:
        raise field_error(field, "This field may not be null.", in_config=True)
    if not isinstance(value, dict):
        raise field_error(field, "Expected a dictionary of items.", in_config=True)
    return value


def optional_string_list_field(
    data: dict[str, Any],
    field: str,
) -> list[str] | None | object:
    if field not in data:
        return _MISSING
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, list):
        raise field_error(field, "Expected a list of items.", in_config=True)
    cleaned = [str(item or "").strip() for item in value]
    filtered = [item for item in cleaned if item]
    return filtered or None


def optional_int_field(
    data: dict[str, Any],
    field: str,
    *,
    min_value: int,
    max_value: int,
) -> int | object:
    if field not in data:
        return _MISSING
    raw = data.get(field)
    if raw is None or raw == "":
        raise field_error(field, "A valid integer is required.", in_config=True)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise field_error(
            field, "A valid integer is required.", in_config=True
        ) from exc

    if value < min_value:
        raise field_error(
            field,
            f"Ensure this value is greater than or equal to {min_value}.",
            in_config=True,
        )
    if value > max_value:
        raise field_error(
            field,
            f"Ensure this value is less than or equal to {max_value}.",
            in_config=True,
        )
    return value


def optional_bool_field(data: dict[str, Any], field: str) -> bool | object:
    if field not in data:
        return _MISSING

    value = data.get(field)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise field_error(field, "Must be a valid boolean.", in_config=True)


def normalize_channel_type(channel_type: str) -> str:
    normalized = str(channel_type or "").strip()
    if normalized not in SUPPORTED_CHANNEL_TYPES:
        raise ChannelConfigValidationError(
            {"type": [f'"{normalized}" is not a valid choice.']}
        )
    return normalized


def normalize_bark_config(config: dict[str, Any]) -> dict[str, Any]:
    raw_base = require_string_field(config, "server_base_url", in_config=True)
    if raw_base.endswith("/push"):
        raw_base = raw_base[: -len("/push")]
    raw_base = raw_base.rstrip("/")

    device_key_raw = optional_string_field(config, "device_key")
    device_key = None if device_key_raw is _MISSING else device_key_raw

    device_keys_raw = optional_string_list_field(config, "device_keys")
    device_keys = None if device_keys_raw is _MISSING else device_keys_raw

    if device_key is None and device_keys is None and raw_base:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(raw_base)
            segments = [
                segment for segment in (parsed.path or "").split("/") if segment
            ]
            if len(segments) == 1:
                segment = segments[0]
                looks_like_key = (
                    len(segment) >= 16
                    and any(char.isdigit() for char in segment)
                    and all(char.isalnum() or char in {"_", "-"} for char in segment)
                )
                if (
                    looks_like_key
                    and parsed.scheme in {"http", "https"}
                    and parsed.netloc
                ):
                    device_key = segment
                    raw_base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        except Exception:
            pass

    if device_key is None and device_keys is None:
        raise ChannelConfigValidationError(
            {"config": {"device_key": ["required (or set device_keys)"]}}
        )

    assert_ssrf_safe(raw_base)

    normalized: dict[str, Any] = {
        "server_base_url": raw_base,
        "device_key": device_key,
        "device_keys": device_keys,
    }
    default_payload = optional_dict_field(config, "default_payload_json")
    if default_payload is not _MISSING:
        normalized["default_payload_json"] = default_payload
    return normalized


def normalize_ntfy_config(config: dict[str, Any]) -> dict[str, Any]:
    server_base_url = require_string_field(config, "server_base_url", in_config=True)
    topic = require_string_field(config, "topic", in_config=True)
    access_token = optional_string_field(config, "access_token")
    username = optional_string_field(config, "username")
    password_raw = config.get("password") if "password" in config else _MISSING
    password = (
        _MISSING
        if password_raw is _MISSING
        else (None if password_raw is None else str(password_raw))
    )

    if access_token not in {_MISSING, None} and (
        username not in {_MISSING, None} or password not in {_MISSING, None, ""}
    ):
        raise config_non_field_error("choose_one_auth_method")

    username_value = None if username is _MISSING else username
    password_value = None if password is _MISSING else password
    if (username_value and not password_value) or (
        password_value and not username_value
    ):
        raise config_non_field_error("username_password_required")

    assert_ssrf_safe(build_topic_url(server_base_url, topic))

    normalized: dict[str, Any] = {
        "server_base_url": server_base_url,
        "topic": topic,
    }
    if access_token is not _MISSING:
        normalized["access_token"] = access_token
    if username is not _MISSING:
        normalized["username"] = username
    if password is not _MISSING:
        normalized["password"] = password

    default_headers = optional_dict_field(config, "default_headers_json")
    if default_headers is not _MISSING:
        normalized["default_headers_json"] = default_headers
    return normalized


def normalize_mqtt_config(config: dict[str, Any]) -> dict[str, Any]:
    broker_host = require_string_field(config, "broker_host", in_config=True)
    topic = require_string_field(config, "topic", in_config=True)
    assert_host_ssrf_safe(broker_host, block_private_networks=True)

    broker_port = optional_int_field(
        config, "broker_port", min_value=1, max_value=65535
    )
    username = optional_string_field(config, "username")
    password_raw = config.get("password") if "password" in config else _MISSING
    password = (
        _MISSING
        if password_raw is _MISSING
        else (None if password_raw is None else str(password_raw))
    )
    tls = optional_bool_field(config, "tls")
    tls_insecure = optional_bool_field(config, "tls_insecure")
    qos = optional_int_field(config, "qos", min_value=0, max_value=2)
    retain = optional_bool_field(config, "retain")
    client_id = optional_string_field(config, "client_id")
    keepalive_seconds = optional_int_field(
        config, "keepalive_seconds", min_value=1, max_value=3600
    )

    username_value = None if username is _MISSING else username
    password_value = None if password is _MISSING else password
    if (username_value and password_value is None) or (
        password_value and not username_value
    ):
        raise config_non_field_error("username_password_required")

    normalized: dict[str, Any] = {
        "broker_host": broker_host,
        "topic": topic,
    }
    if broker_port is not _MISSING:
        normalized["broker_port"] = broker_port
    if username is not _MISSING:
        normalized["username"] = username
    if password is not _MISSING:
        normalized["password"] = password
    if tls is not _MISSING:
        normalized["tls"] = tls
    if tls_insecure is not _MISSING:
        normalized["tls_insecure"] = tls_insecure
    if qos is not _MISSING:
        normalized["qos"] = qos
    if retain is not _MISSING:
        normalized["retain"] = retain
    if client_id is not _MISSING:
        normalized["client_id"] = client_id
    if keepalive_seconds is not _MISSING:
        normalized["keepalive_seconds"] = keepalive_seconds
    return normalized


def normalize_gotify_config(config: dict[str, Any]) -> dict[str, Any]:
    server_base_url = require_string_field(config, "server_base_url", in_config=True)

    from urllib.parse import urlparse

    parsed = urlparse(server_base_url)
    if parsed.scheme not in {"http", "https"}:
        raise field_error(
            "server_base_url", "URL must use http or https.", in_config=True
        )
    if not parsed.netloc:
        raise field_error("server_base_url", "Invalid URL format.", in_config=True)

    server_base_url = server_base_url.rstrip("/")
    assert_ssrf_safe(server_base_url)

    app_token = require_string_field(config, "app_token", in_config=True)
    default_priority = optional_int_field(
        config, "default_priority", min_value=0, max_value=10
    )
    default_extras_json = optional_dict_field(config, "default_extras_json")
    default_payload_json = optional_dict_field(config, "default_payload_json")

    normalized: dict[str, Any] = {
        "server_base_url": server_base_url,
        "app_token": app_token,
    }
    if default_priority is not _MISSING:
        normalized["default_priority"] = default_priority
    if default_extras_json is not _MISSING:
        normalized["default_extras_json"] = default_extras_json
    if default_payload_json is not _MISSING:
        normalized["default_payload_json"] = default_payload_json
    return normalized


def _normalize_channel_config(
    channel_type: str, config: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ChannelConfigValidationError(
            {"config": ["Expected a dictionary of items."]}
        )

    if channel_type == CHANNEL_TYPE_BARK:
        return normalize_bark_config(config)
    if channel_type == CHANNEL_TYPE_NTFY:
        return normalize_ntfy_config(config)
    if channel_type == CHANNEL_TYPE_MQTT:
        return normalize_mqtt_config(config)
    if channel_type == CHANNEL_TYPE_GOTIFY:
        return normalize_gotify_config(config)
    raise ChannelConfigValidationError(
        {"type": [f'"{channel_type}" is not a valid choice.']}
    )


__all__ = [
    "CHANNEL_TYPE_BARK",
    "CHANNEL_TYPE_GOTIFY",
    "CHANNEL_TYPE_MQTT",
    "CHANNEL_TYPE_NTFY",
    "SUPPORTED_CHANNEL_TYPES",
    "_normalize_channel_config",
    "normalize_channel_type",
]
