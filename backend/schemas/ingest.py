from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestEndpointCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class IngestEndpointUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class IngestEndpoint(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    class Config:
        from_attributes = True


class IngestMessageResponse(BaseModel):
    message_id: UUID


class IngestEndpointsResponse(BaseModel):
    endpoints: list[IngestEndpoint]


class IngestEndpointResponse(BaseModel):
    endpoint: IngestEndpoint


class IngestEndpointCreateResponse(BaseModel):
    endpoint: IngestEndpoint
    ingest_key: str
    ingest_url: str


__all__ = [
    "IngestEndpoint",
    "IngestEndpointCreateRequest",
    "IngestEndpointCreateResponse",
    "IngestEndpointResponse",
    "IngestEndpointUpdateRequest",
    "IngestEndpointsResponse",
    "IngestMessageResponse",
]
