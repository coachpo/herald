from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_tables, serialize_uuid


async def build_edge_config(*, session: AsyncSession) -> dict[str, Any]:
    tables = await get_tables()
    rows = (
        await session.execute(
            select(
                tables.ingest_endpoints.c.id,
                tables.ingest_endpoints.c.key_sha256,
            )
            .join(tables.users, tables.ingest_endpoints.c.user_id == tables.users.c.id)
            .where(
                tables.users.c.is_active.is_(True),
                tables.ingest_endpoints.c.revoked_at.is_(None),
                tables.ingest_endpoints.c.deleted_at.is_(None),
            )
            .order_by(tables.ingest_endpoints.c.id)
        )
    ).all()

    ingest_endpoints = [
        {"id": serialize_uuid(row.id), "key_sha256": str(row.key_sha256)}
        for row in rows
    ]
    version_payload = {"ingest_endpoints": ingest_endpoints}
    config = {
        "version": sha256(
            json.dumps(version_payload, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()[:16],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ingest_endpoints": ingest_endpoints,
    }
    return config
