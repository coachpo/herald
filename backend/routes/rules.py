from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..database import get_session
from ..models import (
    Rule,
    RuleCreateRequest,
    RuleResponse,
    RuleUpdateRequest,
    RulesResponse,
)
from ..requests import (
    AllRulesTestResponse,
    MatchPreview,
    RuleTestResponse,
    TestAllRulesRequest,
    TestRuleRequest,
)
from ..services.exceptions import NotFoundError, TemporarilyUnavailableError
from ..services.rules import (
    create_rule as create_rule_service,
    delete_rule as delete_rule_service,
    get_rule_detail as get_rule_detail_service,
    list_rules as list_rules_service,
    preview_all_rules as preview_all_rules_service,
    preview_single_rule as preview_single_rule_service,
    update_rule as update_rule_service,
)

router = APIRouter()


@router.get("/rules", response_model=RulesResponse)
async def list_rules(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """List all forwarding rules."""
    rules = await list_rules_service(session=session, user_id=UUID(user_id))
    return RulesResponse(rules=rules)


@router.post("/rules", response_model=RuleResponse, status_code=201)
async def create_rule_route(
    req: RuleCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        rule_dict = await create_rule_service(
            session=session,
            user_id=UUID(user_id),
            name=req.name,
            enabled=req.enabled,
            channel_id=req.channel_id,
            filter_json=req.filter,
            payload_template=req.payload_template,
        )
    except NotFoundError as exc:
        from . import _not_found_error

        raise _not_found_error(exc.message)
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return RuleResponse(rule=Rule(**rule_dict))


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get single forwarding rule."""
    try:
        rule = await get_rule_detail_service(
            session=session,
            user_id=UUID(user_id),
            rule_id=rule_id,
        )
        return RuleResponse(rule=rule)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="rule_not_found")


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule_route(
    rule_id: UUID,
    req: RuleUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        rule_dict = await update_rule_service(
            session=session,
            user_id=UUID(user_id),
            id=rule_id,
            name=req.name,
            enabled=req.enabled,
            channel_id=req.channel_id,
            filter_json=req.filter,
            payload_template=req.payload_template,
        )
    except NotFoundError as exc:
        from . import _not_found_error

        raise _not_found_error(exc.message)
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return RuleResponse(rule=Rule(**rule_dict))


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule_route(
    rule_id: UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_rule_service(
            session=session,
            user_id=UUID(user_id),
            id=rule_id,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()
    except TemporarilyUnavailableError:
        from . import _temporarily_unavailable_error

        raise _temporarily_unavailable_error()

    return Response(status_code=204)


@router.post("/rules/{rule_id}/test", response_model=RuleTestResponse)
async def test_single_rule_route(
    rule_id: UUID,
    req: TestRuleRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await preview_single_rule_service(
            session=session,
            user_id=UUID(user_id),
            rule_id=rule_id,
            ingest_endpoint_id=req.ingest_endpoint_id,
            payload=req.payload,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()

    return RuleTestResponse(**result)


@router.post("/rules/test", response_model=AllRulesTestResponse)
async def test_all_rules_route(
    req: TestAllRulesRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await preview_all_rules_service(
            session=session,
            user_id=UUID(user_id),
            ingest_endpoint_id=req.ingest_endpoint_id,
            payload=req.payload,
        )
    except NotFoundError:
        from . import _not_found_error

        raise _not_found_error()

    matches = [MatchPreview(**m) for m in result["matches"]]
    return AllRulesTestResponse(
        matched_count=result["matched_count"],
        total_rules=result["total_rules"],
        matches=matches,
    )
