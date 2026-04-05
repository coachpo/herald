"""Django-compatible PBKDF2-SHA256 password hashing.

Produces and verifies hashes in Django's stored format:
    pbkdf2_sha256$<iterations>$<salt>$<base64_hash>

Compatible with Django 5.2 defaults (1_000_000 iterations, 22-char salt,
SHA-256 digest, base64-encoded 32-byte derived key).
"""

from __future__ import annotations

import base64
import hashlib
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 1_000_000
_SALT_LENGTH = 22
_SALT_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def make_password(
    password: str, *, salt: str | None = None, iterations: int = _ITERATIONS
) -> str:
    if salt is None:
        salt = "".join(secrets.choice(_SALT_CHARS) for _ in range(_SALT_LENGTH))

    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"{_ALGORITHM}${iterations}${salt}${hash_b64}"


def check_password(password: str, encoded: str | None) -> bool:
    if not encoded or "$" not in encoded:
        return False

    parts = encoded.split("$", 3)
    if len(parts) != 4 or parts[0] != _ALGORITHM:
        return False

    try:
        iterations = int(parts[1])
    except (ValueError, TypeError):
        return False

    salt = parts[2]
    candidate = make_password(password, salt=salt, iterations=iterations)
    return secrets.compare_digest(encoded, candidate)
