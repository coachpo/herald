from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from ..models import AuthSessionResponse, User, UserResponse


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
    response = JSONResponse(
        content=session_response.model_dump(mode="json"),
    )
    response.headers["Cache-Control"] = "no-store"
    return response
