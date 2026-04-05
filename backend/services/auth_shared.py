from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_tables, serialize_uuid

logger = structlog.get_logger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def utcnow() -> datetime:
    return datetime.now(tz.utc)


def build_user_dict(user: Any) -> dict[str, Any]:
    return {
        "id": UUID(serialize_uuid(user.id)),
        "email": user.email,
        "email_verified_at": user.email_verified_at,
        "created_at": user.created_at,
    }


async def fetch_user_by_email(
    session: AsyncSession,
    email: str,
    *,
    active_only: bool = False,
) -> Any | None:
    tables = await get_tables()
    query = select(tables.users).where(tables.users.c.email == normalize_email(email))
    if active_only:
        query = query.where(tables.users.c.is_active.is_(True))
    result = await session.execute(query)
    return result.fetchone()


async def fetch_user_by_id(session: AsyncSession, user_id: UUID) -> Any | None:
    tables = await get_tables()
    result = await session.execute(
        select(tables.users).where(tables.users.c.id == user_id)
    )
    return result.fetchone()


__all__ = [
    "build_user_dict",
    "fetch_user_by_email",
    "fetch_user_by_id",
    "logger",
    "normalize_email",
    "utcnow",
]
