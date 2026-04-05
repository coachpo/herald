from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def _get_fernet(key: str) -> Fernet:
    if not key:
        raise ValueError("encryption_key_required")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError):
        derived = hashlib.sha256(key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_config(plaintext: str, key: str) -> str:
    fernet = _get_fernet(key)
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_config(ciphertext: str, key: str) -> str:
    fernet = _get_fernet(key)
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


@lru_cache(maxsize=1)
def _fernet_from_settings() -> Fernet:
    from ..config import get_settings

    settings = get_settings()
    key = str(settings.channel_config_encryption_key or "").strip()
    if key:
        try:
            return Fernet(key.encode("utf-8"))
        except (TypeError, ValueError):
            derived = hashlib.sha256(key.encode("utf-8")).digest()
            return Fernet(base64.urlsafe_b64encode(derived))

    derived = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_json_bytes(plaintext: bytes) -> str:
    return _fernet_from_settings().encrypt(plaintext).decode("utf-8")


def decrypt_json_bytes(ciphertext: str) -> bytes:
    return _fernet_from_settings().decrypt(ciphertext.encode("utf-8"))
