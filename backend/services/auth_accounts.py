from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.passwords import check_password, make_password
from ..auth.sessions import revoke_all_refresh_tokens
from ..database import get_tables
from .auth_shared import (
    build_user_dict,
    fetch_user_by_email,
    fetch_user_by_id,
    logger,
    normalize_email,
    utcnow,
)
from .exceptions import (
    EmailTakenError,
    InvalidCredentialsError,
    SignupDisabledError,
    _require_row,
)


async def signup_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    allow_signup: bool = True,
) -> dict[str, Any]:
    if not allow_signup:
        raise SignupDisabledError()

    if await fetch_user_by_email(session, email):
        raise EmailTakenError()

    tables = await get_tables()
    created_user_id = uuid4()
    now = utcnow()

    insert_query = tables.users.insert().values(
        id=created_user_id,
        email=normalize_email(email),
        password=make_password(password),
        is_active=True,
        is_staff=False,
        is_superuser=False,
        created_at=now,
        email_verified_at=None,
    )

    try:
        await session.execute(insert_query)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise EmailTakenError() from exc

    user = _require_row(await fetch_user_by_id(session, created_user_id))
    return build_user_dict(user)


async def change_user_email(
    session: AsyncSession,
    *,
    user_id: UUID,
    new_email: str,
) -> dict[str, Any]:
    tables = await get_tables()

    update_query = (
        update(tables.users)
        .where(tables.users.c.id == user_id)
        .values(email=normalize_email(new_email), email_verified_at=None)
    )

    try:
        await session.execute(update_query)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise EmailTakenError() from exc

    user = _require_row(await fetch_user_by_id(session, user_id))
    return build_user_dict(user)


async def change_user_password(
    session: AsyncSession,
    *,
    user_id: UUID,
    old_password: str,
    new_password: str,
) -> None:
    tables = await get_tables()
    user = await fetch_user_by_id(session, user_id)

    if not user or not check_password(old_password, user.password):
        raise InvalidCredentialsError()

    await session.execute(
        update(tables.users)
        .where(tables.users.c.id == user_id)
        .values(password=make_password(new_password))
    )
    await session.commit()

    await revoke_all_refresh_tokens(
        session=session,
        user_id=user_id,
        reason="password_changed",
    )


async def delete_user_account(
    session: AsyncSession,
    *,
    user_id: UUID,
    password: str,
) -> None:
    tables = await get_tables()
    user = await fetch_user_by_id(session, user_id)

    if not user or not check_password(password, user.password):
        raise InvalidCredentialsError()

    now = utcnow()

    await revoke_all_refresh_tokens(
        session=session,
        user_id=user_id,
        reason="account_deleted",
    )
    await session.execute(
        update(tables.ingest_endpoints)
        .where(
            tables.ingest_endpoints.c.user_id == user_id,
            tables.ingest_endpoints.c.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.execute(tables.users.delete().where(tables.users.c.id == user_id))
    await session.commit()

    logger.info("account_deleted", user_id=str(user_id), email=user.email)


__all__ = [
    "change_user_email",
    "change_user_password",
    "delete_user_account",
    "signup_user",
]
