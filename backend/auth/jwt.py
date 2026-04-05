"""JWT authentication for FastAPI."""

from __future__ import annotations

import time
from typing import Any

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings


def issue_access_token(user_id: str, email: str) -> str:
    """Issue JWT access token."""
    settings = get_settings()
    now = int(time.time())
    exp = now + settings.jwt_access_ttl_seconds
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_signing_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="token_expired") from e
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="invalid_token") from e


# FastAPI dependency for JWT authentication
security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """FastAPI dependency to extract user_id from JWT."""
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_token")

    return user_id


async def get_verified_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """FastAPI dependency requiring verified email (for write operations)."""
    from sqlalchemy import select
    from ..database import get_session, get_tables

    token = credentials.credentials
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_token")

    tables = await get_tables()
    async for session in get_session():
        query = select(tables.users.c.email_verified_at).where(
            tables.users.c.id == user_id
        )
        result = await session.execute(query)
        row = result.fetchone()

        if not row or row[0] is None:
            raise HTTPException(status_code=403, detail="email_not_verified")
        break

    return user_id
