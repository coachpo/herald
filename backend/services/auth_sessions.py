from __future__ import annotations

from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import issue_access_token
from ..auth.passwords import check_password
from ..auth.sessions import (
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..auth.tokens import hash_token
from .auth_shared import build_user_dict, fetch_user_by_email, fetch_user_by_id, logger
from .exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    MissingRefreshTokenError,
    TemporarilyUnavailableError,
)


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


__all__ = ["login_user", "logout_user", "refresh_session"]
