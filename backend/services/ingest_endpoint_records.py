from __future__ import annotations

from typing import Any
from uuid import UUID

from ..database import serialize_uuid
from ..models import IngestEndpoint


def ingest_endpoint_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": UUID(serialize_uuid(row.id)),
        "name": str(row.name),
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
        "revoked_at": row.revoked_at,
    }


def ingest_endpoint_from_row(row: Any) -> IngestEndpoint:
    return IngestEndpoint(**ingest_endpoint_to_dict(row))


__all__ = ["ingest_endpoint_from_row", "ingest_endpoint_to_dict"]
