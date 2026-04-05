from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, get_current_user
from ..database import get_session
from ..edge_config import build_edge_config
from ..models import EdgeConfigResponse

from .channels import router as channels_router
from .ingest_endpoints import router as ingest_endpoints_router
from .messages import router as messages_router
from .rules import router as rules_router
from .auth import router as auth_router
from .ingest import router as ingest_router

router = APIRouter(prefix="/api")

router.include_router(messages_router)
router.include_router(channels_router)
router.include_router(rules_router)
router.include_router(ingest_endpoints_router)


# ── Shared error helpers ────────────────────────────────────────────────


def _not_found_error(message: str = "not found") -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "not_found", "message": message},
    )


def _temporarily_unavailable_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "temporarily_unavailable", "message": "try again"},
    )


def _validation_error(
    details: dict[str, object],
    *,
    message: str = "invalid request",
) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": "validation_error", "message": message, "details": details},
    )


def _channel_test_failed_error(error: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "code": "channel_test_failed",
            "message": "send failed",
            "details": {"error": error},
        },
    )


# ── Edge config endpoint ────────────────────────────────────────────────


@router.get("/edge-config", response_model=EdgeConfigResponse)
async def get_edge_config(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    config = await build_edge_config(session=session, user_id=current_user.id)
    return EdgeConfigResponse(**config)
