from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = ''
    body: str = Field(min_length=1)
    priority: StrictInt = Field(default=3, ge=1, le=5)
    target_ids: list[str] | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class TargetInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    kind: Literal['bark', 'ntfy', 'mqtt', 'gotify']
    config: dict
    is_default: bool = False
    enabled: bool = True
