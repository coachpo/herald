from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool
    channel_id: UUID
    filter: dict[str, Any] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)


class RuleUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool
    channel_id: UUID
    filter: dict[str, Any] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)


class Rule(BaseModel):
    id: UUID
    name: str
    enabled: bool
    channel_id: UUID
    filter: dict[str, Any] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RulesResponse(BaseModel):
    rules: list[Rule]


class RuleResponse(BaseModel):
    rule: Rule


class TestRuleRequest(BaseModel):
    ingest_endpoint_id: UUID
    payload: dict[str, Any]


class TestAllRulesRequest(BaseModel):
    ingest_endpoint_id: UUID
    payload: dict[str, Any]


class RuleTestResponse(BaseModel):
    matches: bool
    channel_type: str
    rendered_payload: dict[str, Any]


class MatchPreview(BaseModel):
    rule: dict[str, Any]
    channel: dict[str, Any]
    channel_type: str
    rendered_payload: dict[str, Any]


class AllRulesTestResponse(BaseModel):
    matched_count: int
    total_rules: int
    matches: list[MatchPreview]


__all__ = [
    "AllRulesTestResponse",
    "MatchPreview",
    "Rule",
    "RuleCreateRequest",
    "RuleResponse",
    "RuleTestResponse",
    "RuleUpdateRequest",
    "RulesResponse",
    "TestAllRulesRequest",
    "TestRuleRequest",
]
