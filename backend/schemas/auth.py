from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class User(BaseModel):
    id: UUID
    email: str
    email_verified_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    user: User


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: User


class SignupRequest(BaseModel):
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password_too_short")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password_too_short")
        return v


class ChangeEmailRequest(BaseModel):
    new_email: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password_too_short")
        return v


class DeleteAccountRequest(BaseModel):
    password: str


__all__ = [
    "AuthSessionResponse",
    "ChangeEmailRequest",
    "ChangePasswordRequest",
    "DeleteAccountRequest",
    "ForgotPasswordRequest",
    "LoginRequest",
    "LogoutRequest",
    "RefreshRequest",
    "ResetPasswordRequest",
    "SignupRequest",
    "User",
    "UserResponse",
    "VerifyEmailRequest",
]
