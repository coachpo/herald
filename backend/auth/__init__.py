from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session, get_tables
from .jwt import decode_access_token


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str


def _auth_error(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedUser:
    if not authorization:
        raise _auth_error("Authentication credentials were not provided.")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _auth_error("invalid_authorization")

    token = parts[1]
    payload = decode_access_token(token)

    subject = payload.get("sub")
    if not subject:
        raise _auth_error("invalid_token")

    try:
        user_id = uuid.UUID(str(subject))
    except ValueError as exc:
        raise _auth_error("invalid_token") from exc

    tables = await get_tables()

    row = (
        await session.execute(
            select(
                tables.users.c.id,
                tables.users.c.email,
                tables.users.c.is_active,
            ).where(tables.users.c.id == user_id)
        )
    ).one_or_none()

    if row is None:
        raise _auth_error("invalid_user")
    if not bool(row.is_active):
        raise _auth_error("inactive_user")

    return AuthenticatedUser(id=user_id, email=str(row.email))
