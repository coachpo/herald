from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..config import get_settings
from ..database import get_session
from ..models import UserResponse
from ..requests import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    SignupRequest,
)
from ..services.auth_accounts import (
    change_user_email,
    change_user_password,
    delete_user_account,
    signup_user,
)
from ..services.auth_tokens import resend_verification_email
from ..services.auth_users import get_user_profile
from ..services.exceptions import (
    EmailTakenError,
    InvalidCredentialsError,
    SignupDisabledError,
)

from .auth_common import build_user_response

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(
    req: SignupRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user_dict = await signup_user(
            session=session,
            email=req.email,
            password=req.password,
            allow_signup=get_settings().allow_user_signup,
        )
    except SignupDisabledError:
        raise HTTPException(
            status_code=403,
            detail={"code": "signup_disabled", "message": "signup disabled"},
        )
    except EmailTakenError:
        raise HTTPException(
            status_code=400,
            detail={"code": "email_taken", "message": "email already in use"},
        )

    return build_user_response(user_dict)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    user_dict = await get_user_profile(session=session, user_id=UUID(user_id))
    if user_dict is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "user not found"},
        )
    return build_user_response(user_dict)


@router.post("/resend-verification", status_code=204)
async def resend_verification(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    await resend_verification_email(session=session, user_id=UUID(user_id))
    return Response(status_code=204)


@router.post("/change-email", response_model=UserResponse)
async def change_email(
    req: ChangeEmailRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        user_dict = await change_user_email(
            session=session,
            user_id=UUID(user_id),
            new_email=req.new_email,
        )
    except EmailTakenError:
        raise HTTPException(
            status_code=400,
            detail={"code": "email_taken", "message": "email already in use"},
        )

    return build_user_response(user_dict)


@router.post("/change-password", status_code=204)
async def change_password(
    req: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await change_user_password(
            session=session,
            user_id=UUID(user_id),
            old_password=req.old_password,
            new_password=req.new_password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_credentials",
                "message": "invalid current password",
            },
        )

    return Response(status_code=204)


@router.post("/delete-account", status_code=204)
async def delete_account(
    req: DeleteAccountRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    try:
        await delete_user_account(
            session=session,
            user_id=UUID(user_id),
            password=req.password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "invalid password"},
        )

    return Response(status_code=204)
