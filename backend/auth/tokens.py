import hashlib
import hmac
import secrets

from ..config import get_settings


def generate_secret_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """HMAC-SHA256 hash a raw token using SECRET_KEY."""
    fastapi_settings = get_settings()
    key = fastapi_settings.secret_key.encode("utf-8")
    msg = raw_token.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def sha256_hex(raw_token: str) -> str:
    """Unkeyed SHA-256 hex digest for the edge-relay offline verifier."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
