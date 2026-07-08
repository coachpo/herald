from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EdgeIngestEndpoint(BaseModel):
    id: UUID
    key_sha256: str


class EdgeConfigResponse(BaseModel):
    version: str
    updated_at: datetime
    ingest_endpoints: list[EdgeIngestEndpoint]


__all__ = ["EdgeConfigResponse", "EdgeIngestEndpoint"]
