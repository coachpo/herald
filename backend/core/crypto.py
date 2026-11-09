"""Authenticated encryption for destination credentials."""
from cryptography.fernet import Fernet


def encrypt_json_bytes(plaintext: bytes, key: str) -> str:
    return Fernet(key.encode()).encrypt(plaintext).decode()


def decrypt_json_bytes(ciphertext: str, key: str) -> bytes:
    return Fernet(key.encode()).decrypt(ciphertext.encode())
