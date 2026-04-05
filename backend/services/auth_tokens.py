from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.passwords import make_password
from ..auth.sessions import revoke_all_refresh_tokens
from ..auth.tokens import generate_secret_token, hash_token
from ..database import get_tables, serialize_uuid
from .auth_shared import fetch_user_by_email, fetch_user_by_id, logger, utcnow
from .exceptions import InvalidTokenError


async def verify_email_token(
    session: AsyncSession,
    *,
    token: str,
) -> None:
    tables = await get_tables()
    token_hash_value = hash_token(token)
    now = utcnow()

    result = await session.execute(
        select(tables.email_verification_tokens).where(
            tables.email_verification_tokens.c.token_hash == token_hash_value,
        )
    )
    row = result.fetchone()

    if not row or row.used_at is not None or row.expires_at <= now:
        raise InvalidTokenError()

    await session.execute(
        update(tables.users)
        .where(tables.users.c.id == row.user_id)
        .values(email_verified_at=now)
    )
    await session.execute(
        update(tables.email_verification_tokens)
        .where(tables.email_verification_tokens.c.id == row.id)
        .values(used_at=now)
    )
    await session.commit()


async def resend_verification_email(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> None:
    tables = await get_tables()
    user = await fetch_user_by_id(session, user_id)

    if not user or user.email_verified_at is not None:
        return

    now = utcnow()
    raw = generate_secret_token(32)
    await session.execute(
        tables.email_verification_tokens.insert().values(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(hours=24),
            used_at=None,
            created_at=now,
        )
    )
    await session.commit()
    logger.info("verification_email_resent", user_id=str(user_id))


async def request_password_reset(
    session: AsyncSession,
    *,
    email: str,
) -> None:
    tables = await get_tables()
    user = await fetch_user_by_email(session, email, active_only=True)

    if not user:
        return

    now = utcnow()
    raw = generate_secret_token(32)
    await session.execute(
        tables.password_reset_tokens.insert().values(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(hours=1),
            used_at=None,
            created_at=now,
        )
    )
    await session.commit()
    logger.info("password_reset_requested", user_id=str(user.id))


async def reset_password(
    session: AsyncSession,
    *,
    token: str,
    new_password: str,
) -> None:
    tables = await get_tables()
    token_hash_value = hash_token(token)
    now = utcnow()

    result = await session.execute(
        select(tables.password_reset_tokens).where(
            tables.password_reset_tokens.c.token_hash == token_hash_value,
        )
    )
    row = result.fetchone()

    if not row or row.used_at is not None or row.expires_at <= now:
        raise InvalidTokenError()

    await session.execute(
        update(tables.users)
        .where(tables.users.c.id == row.user_id)
        .values(password=make_password(new_password))
    )
    await session.execute(
        update(tables.password_reset_tokens)
        .where(tables.password_reset_tokens.c.id == row.id)
        .values(used_at=now)
    )
    await session.commit()

    await revoke_all_refresh_tokens(
        session=session,
        user_id=UUID(serialize_uuid(row.user_id)),
        reason="password_reset",
    )


__all__ = [
    "request_password_reset",
    "resend_verification_email",
    "reset_password",
    "verify_email_token",
]
