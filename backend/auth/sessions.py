"""Refresh token management for FastAPI."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_tables, serialize_uuid


async def create_refresh_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, uuid.UUID]:
    """Create a new refresh token and return (raw_token, token_id)."""
    from .tokens import generate_token, hash_token

    settings = get_settings()
    tables = await get_tables()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)

    # Generate raw token
    raw_token = generate_token()
    token_hash = hash_token(raw_token)

    token_id = uuid.uuid4()
    family_id = token_id

    await session.execute(
        tables.refresh_tokens.insert().values(
            id=token_id.hex,
            user_id=user_id.hex,
            token_hash=token_hash,
            family_id=family_id.hex,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
    )
    await session.commit()

    return raw_token, token_id


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    token_hash: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, Any]:
    """
    Rotate refresh token with family_id tracking.

    Returns: (new_raw_token, refresh_token_row)
    Raises: ValueError if token is invalid, revoked, or expired
    """
    from .tokens import generate_token, hash_token as hash_new_token

    tables = await get_tables()
    now = datetime.now(timezone.utc)

    # Lock and fetch current token
    result = await session.execute(
        select(tables.refresh_tokens)
        .where(tables.refresh_tokens.c.token_hash == token_hash)
        .with_for_update()
    )
    current = result.fetchone()

    if current is None:
        raise ValueError("invalid_refresh")

    # Check if already revoked (reuse detection)
    if current.revoked_at is not None:
        # Revoke entire family
        await session.execute(
            update(tables.refresh_tokens)
            .where(tables.refresh_tokens.c.family_id == current.family_id)
            .where(tables.refresh_tokens.c.revoked_at.is_(None))
            .values(
                revoked_at=now,
                revoked_reason="family_compromised",
                updated_at=now,
            )
        )
        await session.commit()
        raise ValueError("refresh_reused")

    # Check expiration
    if current.expires_at <= now:
        await session.execute(
            update(tables.refresh_tokens)
            .where(tables.refresh_tokens.c.id == current.id)
            .values(
                revoked_at=now,
                revoked_reason="expired",
                updated_at=now,
            )
        )
        await session.commit()
        raise ValueError("refresh_expired")

    # Generate new token
    new_raw_token = generate_token()
    new_token_hash = hash_new_token(new_raw_token)

    # Create new token in same family
    user_id = uuid.UUID(serialize_uuid(current.user_id))
    family_id = uuid.UUID(serialize_uuid(current.family_id))

    settings = get_settings()
    expires_at = now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)
    new_token_id = uuid.uuid4()

    await session.execute(
        tables.refresh_tokens.insert().values(
            id=new_token_id.hex,
            user_id=user_id.hex,
            token_hash=new_token_hash,
            family_id=family_id.hex,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
    )

    # Revoke current token
    await session.execute(
        update(tables.refresh_tokens)
        .where(tables.refresh_tokens.c.id == current.id)
        .values(
            revoked_at=now,
            revoked_reason="rotated",
            replaced_by_id=new_token_id.hex,
            last_used_at=now,
            updated_at=now,
        )
    )
    await session.commit()

    return new_raw_token, current


async def revoke_refresh_token(
    session: AsyncSession,
    *,
    token_hash: str,
    reason: str,
) -> None:
    """Revoke a single refresh token."""
    tables = await get_tables()
    now = datetime.now(timezone.utc)

    await session.execute(
        update(tables.refresh_tokens)
        .where(tables.refresh_tokens.c.token_hash == token_hash)
        .where(tables.refresh_tokens.c.revoked_at.is_(None))
        .values(
            revoked_at=now,
            revoked_reason=reason,
            updated_at=now,
        )
    )
    await session.commit()


async def revoke_all_refresh_tokens(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    reason: str,
) -> None:
    """Revoke all refresh tokens for a user."""
    tables = await get_tables()
    now = datetime.now(timezone.utc)

    user_id_str = user_id.hex

    await session.execute(
        update(tables.refresh_tokens)
        .where(tables.refresh_tokens.c.user_id == user_id_str)
        .where(tables.refresh_tokens.c.revoked_at.is_(None))
        .values(
            revoked_at=now,
            revoked_reason=reason,
            updated_at=now,
        )
    )
    await session.commit()
