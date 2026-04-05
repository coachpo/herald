from __future__ import annotations

import json
from typing import Any


class EmailTakenError(Exception):
    """Email already in use."""

    pass


class InvalidCredentialsError(Exception):
    """Invalid email or password."""

    pass


class MissingRefreshTokenError(Exception):
    """Refresh token not provided."""

    pass


class InvalidTokenError(Exception):
    """Token invalid or expired."""

    pass


class IngestError(Exception):
    def __init__(self, *, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class NotFoundError(Exception):
    def __init__(self, message: str = "not found") -> None:
        super().__init__(message)
        self.message = message


class TemporarilyUnavailableError(Exception):
    """Service temporarily unavailable."""

    pass


class ChannelConfigValidationError(ValueError):
    def __init__(self, details: dict[str, Any]) -> None:
        super().__init__("invalid_channel_config")
        self.details = details


class SignupDisabledError(Exception):
    """User signup is disabled."""

    pass


def _require_row(row: Any | None) -> Any:
    if row is None:
        raise TemporarilyUnavailableError()
    return row


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


__all__ = [
    "EmailTakenError",
    "InvalidCredentialsError",
    "MissingRefreshTokenError",
    "InvalidTokenError",
    "IngestError",
    "NotFoundError",
    "TemporarilyUnavailableError",
    "ChannelConfigValidationError",
    "SignupDisabledError",
    "_require_row",
    "_json_object",
]
