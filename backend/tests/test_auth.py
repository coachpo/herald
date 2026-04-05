"""Test JWT authentication."""

import time

import pytest

from backend.auth.jwt import issue_access_token, decode_access_token
from backend.config import get_settings


class TestJWT:
    """Test JWT token operations."""

    def test_issue_and_decode_token(self):
        """Issue and decode should roundtrip."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        email = "test@example.com"

        token = issue_access_token(user_id, email)
        payload = decode_access_token(token)

        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert "iat" in payload
        assert "exp" in payload

    def test_expired_token_rejected(self):
        """Expired tokens should be rejected."""
        # Create token with negative TTL (already expired)
        settings = get_settings()
        original_ttl = settings.jwt_access_ttl_seconds

        try:
            settings.jwt_access_ttl_seconds = -1
            token = issue_access_token("user-id", "test@example.com")

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                decode_access_token(token)

            assert exc_info.value.status_code == 401
            assert "token_expired" in str(exc_info.value.detail)
        finally:
            settings.jwt_access_ttl_seconds = original_ttl

    def test_invalid_token_rejected(self):
        """Invalid tokens should be rejected."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.here")

        assert exc_info.value.status_code == 401
        assert "invalid_token" in str(exc_info.value.detail)

    def test_token_with_wrong_signature_rejected(self):
        """Tokens signed with different key should be rejected."""
        import jwt

        payload = {
            "sub": "user-id",
            "email": "test@example.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }

        # Sign with wrong key
        wrong_token = jwt.encode(payload, "wrong-key", algorithm="HS256")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(wrong_token)

        assert exc_info.value.status_code == 401
