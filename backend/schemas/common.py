from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "unknown"
    version: str = "unknown"


__all__ = ["HealthResponse"]
