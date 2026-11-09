from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator


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


class _RoutingModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class PriorityCondition(_RoutingModel):
    field: Literal['priority']
    op: Literal['eq', 'gte', 'lte']
    value: StrictInt = Field(ge=1, le=5)


class TextCondition(_RoutingModel):
    field: Literal['title', 'body']
    op: Literal['eq', 'prefix', 'contains']
    value: str


RoutingCondition = Annotated[PriorityCondition | TextCondition, Field(discriminator='field')]


class RoutingRule(_RoutingModel):
    id: str = Field(min_length=1)
    enabled: StrictBool = True
    all: list[RoutingCondition] = Field(min_length=1)
    target_ids: list[str] = Field(min_length=1)

    @field_validator('target_ids')
    @classmethod
    def normalize_targets(cls, value: list[str]) -> list[str]:
        if any(not target_id for target_id in value):
            raise ValueError('target IDs must be nonempty')
        return sorted(set(value))


class RoutingInput(_RoutingModel):
    revision: StrictInt = Field(ge=0)
    rules: list[RoutingRule]

    @model_validator(mode='after')
    def unique_rule_ids(self) -> Self:
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError('rule IDs must be unique')
        return self
