from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import AuthSessionResponse
from ..requests import LoginRequest, LogoutRequest, RefreshRequest
from ..services.auth_sessions import login_user, logout_user, refresh_session
from ..services.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    MissingRefreshTokenError,
    TemporarilyUnavailableError,
)

from .auth_common import build_session_response, client_ip, user_agent

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        access_token, refresh_token, user_dict = await login_user(
            session=session,
            email=req.email,
            password=req.password,
            ip=client_ip(request),
            user_agent=user_agent(request),
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "invalid credentials"},
        )

    return build_session_response(
        access_token=access_token,
        refresh_token=refresh_token,
        user_dict=user_dict,
    )


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh(
    req: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        access_token, new_refresh_token, user_dict = await refresh_session(
            session=session,
            refresh_token=req.refresh_token,
            ip=client_ip(request),
            user_agent=user_agent(request),
        )
    except MissingRefreshTokenError:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "missing refresh token"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "invalid refresh token"},
        )
    except TemporarilyUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={"code": "temporarily_unavailable", "message": "try again"},
        )

    return build_session_response(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_dict=user_dict,
    )


@router.post("/logout", status_code=204)
async def logout(
    req: LogoutRequest,
    session: AsyncSession = Depends(get_session),
):
    await logout_user(session=session, refresh_token=req.refresh_token or "")
    return Response(status_code=204)
