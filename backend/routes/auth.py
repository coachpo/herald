from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_current_user_id
from ..config import get_settings
from ..database import get_session
from ..schemas.auth import (
    AuthSessionResponse,
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    User,
    UserResponse,
)
from ..services.auth import (
    change_user_email,
    change_user_password,
    delete_user_account,
    get_user_profile,
    login_user,
    logout_user,
    refresh_session,
    signup_user,
)
from ..services.exceptions import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    MissingRefreshTokenError,
    SignupDisabledError,
    TemporarilyUnavailableError,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def build_user_response(user_dict: dict[str, object]) -> UserResponse:
    return UserResponse(user=User.model_validate(user_dict))


def build_session_response(
    *,
    access_token: str,
    refresh_token: str,
    user_dict: dict[str, object],
) -> JSONResponse:
    user = User.model_validate(user_dict)
    session_response = AuthSessionResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )
    response = JSONResponse(content=session_response.model_dump(mode="json"))
    response.headers["Cache-Control"] = "no-store"
    return response


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
