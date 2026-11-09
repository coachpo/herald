from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.models import MessageInput, RoutingInput, RoutingRule
from backend.routing import match_rules


def rule(rule_id='primary', *, conditions=None, target_ids=None, **changes):
    return {
        'id': rule_id,
        'all': conditions if conditions is not None else [{'field': 'priority', 'op': 'gte', 'value': 3}],
        'target_ids': target_ids if target_ids is not None else ['target-a'],
        **changes,
    }


@pytest.mark.parametrize(('op', 'priority', 'threshold', 'matched'), [
    ('eq', 1, 1, True), ('eq', 5, 5, True), ('eq', 3, 4, False),
    ('gte', 1, 1, True), ('gte', 5, 5, True), ('gte', 5, 4, True), ('gte', 3, 4, False),
    ('lte', 1, 1, True), ('lte', 5, 5, True), ('lte', 1, 4, True), ('lte', 5, 4, False),
])
def test_priority_operators_include_bounds(op, priority, threshold, matched):
    rules = [rule(conditions=[{'field': 'priority', 'op': op, 'value': threshold}])]
    assert match_rules(rules, {'body': 'message', 'priority': priority}) == (
        (['primary'], ['target-a']) if matched else ([], [])
    )


@pytest.mark.parametrize('field', ['title', 'body'])
@pytest.mark.parametrize(('op', 'value', 'matched'), [
    ('eq', ' Alert: Ready ', True), ('eq', 'Alert: Ready', False),
    ('eq', ' alert: ready ', False), ('eq', 'Alert', False),
    ('prefix', ' Alert:', True), ('prefix', 'Alert:', False),
    ('prefix', ' alert:', False), ('prefix', 'Ready', False),
    ('contains', ': Ready', True), ('contains', 'ready', False),
    ('contains', 'missing', False), ('prefix', '', True), ('contains', '', True),
])
def test_text_operators_preserve_exact_case_and_whitespace(field, op, value, matched):
    rules = [rule(conditions=[{'field': field, 'op': op, 'value': value}])]
    message = {'title': ' Alert: Ready ', 'body': ' Alert: Ready '}
    assert match_rules(rules, message) == ((['primary'], ['target-a']) if matched else ([], []))


def test_message_defaults_are_applied_before_matching():
    rules = [rule(conditions=[
        {'field': 'priority', 'op': 'eq', 'value': 3},
        {'field': 'title', 'op': 'eq', 'value': ''},
    ])]
    assert match_rules(rules, {'body': 'message'}) == (['primary'], ['target-a'])
    assert match_rules(rules, MessageInput(body='message')) == (['primary'], ['target-a'])


@pytest.mark.parametrize('changed', [
    {}, {'title': 'lowercase'}, {'body': 'unrelated'}, {'priority': 3},
])
def test_every_condition_in_a_rule_must_match(changed):
    rules = [rule(conditions=[
        {'field': 'title', 'op': 'prefix', 'value': 'Alert'},
        {'field': 'body', 'op': 'contains', 'value': 'ready'},
        {'field': 'priority', 'op': 'gte', 'value': 4},
    ])]
    message = {'title': 'Alert: Job', 'body': 'Job ready', 'priority': 4, **changed}
    assert match_rules(rules, message) == (([], []) if changed else (['primary'], ['target-a']))


def test_all_matching_rules_merge_targets_without_stopping_or_adding_disabled_targets():
    rules = [
        rule('first', target_ids=['z', 'a', 'z']),
        rule('disabled', target_ids=['disabled-only'], enabled=False),
        rule('missed', target_ids=['miss-only'], conditions=[{'field': 'priority', 'op': 'eq', 'value': 5}]),
        rule('second', target_ids=['b', 'a']),
    ]
    message = {'body': 'message'}
    assert match_rules(rules, message) == (['first', 'second'], ['a', 'b', 'z'])
    assert match_rules(list(reversed(rules)), message) == (['second', 'first'], ['a', 'b', 'z'])


def test_zero_rules_and_zero_matches_return_no_match_ids_or_targets():
    assert match_rules([], {'body': 'message'}) == ([], [])
    assert match_rules([rule(enabled=False)], {'body': 'message'}) == ([], [])
    assert match_rules([rule()], {'body': 'message', 'priority': 1}) == ([], [])


def test_model_normalizes_target_ids_without_rewriting_rule_or_condition_text():
    original = rule('  原文 ID  ', target_ids=['z', ' a ', 'z', 'a'], conditions=[
        {'field': 'title', 'op': 'eq', 'value': '  Écho\n '},
    ])
    configuration = RoutingInput.model_validate({'revision': 0, 'rules': [original]})
    assert configuration.model_dump() == {
        'revision': 0, 'rules': [{**original, 'enabled': True, 'target_ids': [' a ', 'a', 'z']}],
    }
    assert match_rules(configuration.rules, {'title': '  Écho\n ', 'body': 'message'}) == (
        ['  原文 ID  '], [' a ', 'a', 'z'],
    )


@pytest.mark.parametrize('value', [True, False, 0, 6, -1, 3.0, '3', None])
def test_priority_condition_requires_strict_integer_one_through_five(value):
    with pytest.raises(ValidationError):
        RoutingRule.model_validate(rule(conditions=[{'field': 'priority', 'op': 'eq', 'value': value}]))


@pytest.mark.parametrize('condition', [
    {'field': 'priority', 'op': 'contains', 'value': 3},
    {'field': 'priority', 'op': 'prefix', 'value': 3},
    {'field': 'priority', 'op': 'gt', 'value': 3},
    {'field': 'title', 'op': 'gte', 'value': '3'},
    {'field': 'body', 'op': 'lte', 'value': '3'},
    {'field': 'source', 'op': 'eq', 'value': 'job'},
    {'field': 'title', 'op': 'regex', 'value': '.*'},
    {'field': 'title', 'op': 'eq', 'value': 3},
    {'field': 'title', 'op': 'eq', 'value': True},
    {'field': 'body', 'op': 'eq', 'value': None},
    {'field': 'body', 'op': 'eq'},
    {'field': 'body', 'op': 'eq', 'value': 'text', 'extra': True},
    {'op': 'eq', 'value': 'text'},
    {'field': 'body', 'value': 'text'},
])
def test_invalid_condition_types_fields_and_operators_are_rejected(condition):
    with pytest.raises(ValidationError):
        RoutingRule.model_validate(rule(conditions=[condition]))


@pytest.mark.parametrize('changes', [
    {'id': ''}, {'id': 1}, {'id': None},
    {'enabled': 1}, {'enabled': 'true'}, {'enabled': None},
    {'all': []}, {'all': None}, {'all': {}},
    {'target_ids': []}, {'target_ids': ['']}, {'target_ids': [1]},
    {'target_ids': None}, {'target_ids': 'target-a'},
    {'extra': 'value'},
])
def test_invalid_rules_are_rejected(changes):
    with pytest.raises(ValidationError):
        RoutingRule.model_validate({**rule(), **changes})


@pytest.mark.parametrize('revision', [-1, 0.0, '0', True, False, None])
def test_revision_requires_strict_nonnegative_integer(revision):
    with pytest.raises(ValidationError):
        RoutingInput.model_validate({'revision': revision, 'rules': []})


@pytest.mark.parametrize('configuration', [
    {'revision': 0, 'rules': [rule(), rule()]},
    {'revision': 0, 'rules': [], 'extra': True},
    {'revision': 0}, {'rules': []}, {'revision': 0, 'rules': None},
])
def test_duplicate_rule_ids_and_invalid_configuration_are_rejected(configuration):
    with pytest.raises(ValidationError):
        RoutingInput.model_validate(configuration)


def test_empty_rule_array_is_valid_and_matching_does_not_mutate_inputs():
    assert RoutingInput.model_validate({'revision': 0, 'rules': []}).model_dump() == {'revision': 0, 'rules': []}
    rules = [rule(target_ids=['b', 'a', 'a'])]
    message = {'body': 'message'}
    original_rules, original_message = deepcopy(rules), deepcopy(message)
    assert match_rules(rules, message) == (['primary'], ['a', 'b'])
    assert rules == original_rules
    assert message == original_message
