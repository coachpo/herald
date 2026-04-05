from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..requests import ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest
from ..services.auth_tokens import (
    request_password_reset,
    reset_password,
    verify_email_token,
)
from ..services.exceptions import InvalidTokenError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/verify-email", status_code=204)
async def verify_email(
    req: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        await verify_email_token(session=session, token=req.token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_token", "message": "invalid or expired token"},
        )

    return Response(status_code=204)


@router.post("/forgot-password", status_code=204)
async def forgot_password(
    req: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    await request_password_reset(session=session, email=req.email)
    return Response(status_code=204)


@router.post("/reset-password", status_code=204)
async def reset_password_endpoint(
    req: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        await reset_password(
            session=session,
            token=req.token,
            new_password=req.new_password,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_token", "message": "invalid or expired token"},
        )

    return Response(status_code=204)
