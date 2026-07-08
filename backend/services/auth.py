from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import issue_access_token
from ..auth.passwords import check_password, make_password
from ..auth.sessions import (
    create_refresh_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..auth.tokens import hash_token
from ..database import get_tables, serialize_uuid
from .exceptions import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingRefreshTokenError,
    SignupDisabledError,
    TemporarilyUnavailableError,
    _require_row,
)

logger = structlog.get_logger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def utcnow() -> datetime:
    return datetime.now(tz.utc)


def build_user_dict(user: Any) -> dict[str, Any]:
    return {
        "id": UUID(serialize_uuid(user.id)),
        "email": user.email,
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


async def get_user_profile(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> dict[str, Any] | None:
    user = await fetch_user_by_id(session, user_id)
    if user is None:
        return None
    return build_user_dict(user)


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
        created_at=now,
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
        .values(email=normalize_email(new_email))
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


async def login_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, dict[str, Any]]:
    user = await fetch_user_by_email(session, email)

    if not user or not user.is_active or not check_password(password, user.password):
        raise InvalidCredentialsError()

    user_dict = build_user_dict(user)
    access_token = issue_access_token(str(user_dict["id"]), user.email)
    refresh_token, _ = await create_refresh_token(
        session=session,
        user_id=user_dict["id"],
        ip=ip,
        user_agent=user_agent,
    )
    return access_token, refresh_token, user_dict


async def refresh_session(
    session: AsyncSession,
    *,
    refresh_token: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, dict[str, Any]]:
    raw = refresh_token.strip()
    if not raw:
        raise MissingRefreshTokenError()

    try:
        new_raw, refresh_row = await rotate_refresh_token(
            session=session,
            token_hash=hash_token(raw),
            ip=ip,
            user_agent=user_agent,
        )
    except OperationalError as exc:
        logger.exception("refresh_db_error", err=str(exc))
        raise TemporarilyUnavailableError() from exc
    except ValueError as exc:
        raise InvalidTokenError() from exc

    user = await fetch_user_by_id(session, refresh_row.user_id)
    if not user:
        raise InvalidTokenError()

    user_dict = build_user_dict(user)
    access_token = issue_access_token(str(user_dict["id"]), user.email)
    return access_token, new_raw, user_dict


async def logout_user(
    session: AsyncSession,
    *,
    refresh_token: str,
) -> None:
    raw = refresh_token.strip()
    if raw:
        await revoke_refresh_token(
            session=session,
            token_hash=hash_token(raw),
            reason="logout",
        )
