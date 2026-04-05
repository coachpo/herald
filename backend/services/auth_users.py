from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .auth_shared import build_user_dict, fetch_user_by_id


async def get_user_profile(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> dict[str, Any] | None:
    user = await fetch_user_by_id(session, user_id)
    if user is None:
        return None
    return build_user_dict(user)


__all__ = ["get_user_profile"]
