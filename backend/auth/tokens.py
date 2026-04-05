import hashlib
import hmac
import os
import secrets

from ..config import get_settings


def generate_secret_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(nbytes)


# Alias for backward compatibility — sessions.py imports this name.
generate_token = generate_secret_token


def hash_token(raw_token: str) -> str:
    """HMAC-SHA256 hash a raw token using TOKEN_HASH_KEY or SECRET_KEY."""
    fastapi_settings = get_settings()
    cfg = os.environ.get("TOKEN_HASH_KEY", "")
    secret_key = fastapi_settings.secret_key

    key = (cfg or secret_key).encode("utf-8")
    msg = raw_token.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
