from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.tokens import generate_secret_token, hash_token
from ..database import get_tables
from ..models import IngestEndpoint
from .exceptions import NotFoundError
from .ingest_endpoint_records import ingest_endpoint_from_row, ingest_endpoint_to_dict


async def list_ingest_endpoints(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> list[IngestEndpoint]:
    tables = await get_tables()
    result = await session.execute(
        select(tables.ingest_endpoints)
        .where(tables.ingest_endpoints.c.user_id == user_id)
        .where(tables.ingest_endpoints.c.deleted_at.is_(None))
        .order_by(tables.ingest_endpoints.c.created_at.desc())
    )
    return [ingest_endpoint_from_row(row) for row in result.fetchall()]


async def get_ingest_endpoint(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID | str,
    active_only: bool = False,
) -> Any:
    tables = await get_tables()
    endpoint_id = id if isinstance(id, UUID) else UUID(str(id))

    query = select(tables.ingest_endpoints).where(
        tables.ingest_endpoints.c.user_id == user_id,
        tables.ingest_endpoints.c.id == endpoint_id,
    )
    if active_only:
        query = query.where(tables.ingest_endpoints.c.deleted_at.is_(None))

    result = await session.execute(query)
    row = result.fetchone()
    if row is None:
        raise NotFoundError()
    return row


async def get_ingest_endpoint_detail(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID | str,
) -> IngestEndpoint:
    row = await get_ingest_endpoint(session, user_id=user_id, id=id)
    return ingest_endpoint_from_row(row)


async def create_ingest_endpoint(
    session: AsyncSession,
    *,
    user_id: UUID,
    name: str,
    base_url: str,
) -> tuple[dict[str, Any], str, str]:
    tables = await get_tables()
    endpoint_id = uuid4()
    raw_token = generate_secret_token(32)
    now = datetime.now(tz.utc)
    ingest_url = f"{base_url.rstrip('/')}/api/ingest/{endpoint_id.hex}"

    async def _create() -> dict[str, Any]:
        insert_query = tables.ingest_endpoints.insert().values(
            id=endpoint_id,
            user_id=user_id,
            name=name,
            token_hash=hash_token(raw_token),
            created_at=now,
            revoked_at=None,
            last_used_at=None,
            deleted_at=None,
        )
        await session.execute(insert_query)
        await session.commit()
        endpoint = await get_ingest_endpoint(session, user_id=user_id, id=endpoint_id)
        return ingest_endpoint_to_dict(endpoint)

    endpoint_dict = await _create()
    return endpoint_dict, raw_token, ingest_url


async def update_ingest_endpoint(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
    name: str,
) -> dict[str, Any]:
    tables = await get_tables()

    async def _update() -> dict[str, Any]:
        await get_ingest_endpoint(session, user_id=user_id, id=id, active_only=True)
        await session.execute(
            update(tables.ingest_endpoints)
            .where(tables.ingest_endpoints.c.id == id)
            .values(name=name)
        )
        await session.commit()
        endpoint = await get_ingest_endpoint(
            session,
            user_id=user_id,
            id=id,
            active_only=True,
        )
        return ingest_endpoint_to_dict(endpoint)

    return await _update()


async def delete_ingest_endpoint(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> None:
    tables = await get_tables()

    async def _delete() -> None:
        endpoint = await get_ingest_endpoint(
            session,
            user_id=user_id,
            id=id,
            active_only=True,
        )
        now = datetime.now(tz.utc)
        revoked_at = endpoint.revoked_at or now
        await session.execute(
            update(tables.ingest_endpoints)
            .where(tables.ingest_endpoints.c.id == id)
            .values(revoked_at=revoked_at, deleted_at=now)
        )
        await session.commit()

    await _delete()


async def revoke_ingest_endpoint(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> None:
    tables = await get_tables()

    async def _revoke() -> None:
        endpoint = await get_ingest_endpoint(
            session,
            user_id=user_id,
            id=id,
            active_only=True,
        )
        if endpoint.revoked_at is None:
            await session.execute(
                update(tables.ingest_endpoints)
                .where(tables.ingest_endpoints.c.id == id)
                .values(revoked_at=datetime.now(tz.utc))
            )
            await session.commit()

    await _revoke()


__all__ = [
    "list_ingest_endpoints",
    "get_ingest_endpoint",
    "get_ingest_endpoint_detail",
    "create_ingest_endpoint",
    "update_ingest_endpoint",
    "delete_ingest_endpoint",
    "revoke_ingest_endpoint",
]
