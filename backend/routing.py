"""Pure condition matching; durable selection and target checks belong to Store."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import MessageInput, PriorityCondition, RoutingCondition, RoutingRule


def _matches(condition: RoutingCondition, message: MessageInput) -> bool:
    if isinstance(condition, PriorityCondition):
        if condition.op == 'eq':
            return message.priority == condition.value
        if condition.op == 'gte':
            return message.priority >= condition.value
        return message.priority <= condition.value

    value = message.title if condition.field == 'title' else message.body
    if condition.op == 'eq':
        return value == condition.value
    if condition.op == 'prefix':
        return value.startswith(condition.value)
    return condition.value in value


def match_rules(
    rules: Sequence[RoutingRule | Mapping[str, object]],
    message: MessageInput | Mapping[str, object],
) -> tuple[list[str], list[str]]:
    """Return ordered matched rule IDs and the sorted union of their target IDs.

    Raw messages use the existing MessageInput defaults. This function neither
    falls back to default targets nor checks whether target IDs are available.
    """
    normalized = MessageInput.model_validate(message)
    matched_rule_ids: list[str] = []
    target_ids: set[str] = set()
    for value in rules:
        rule = RoutingRule.model_validate(value)
        if rule.enabled and all(_matches(condition, normalized) for condition in rule.all):
            matched_rule_ids.append(rule.id)
            target_ids.update(rule.target_ids)
    return matched_rule_ids, sorted(target_ids)
