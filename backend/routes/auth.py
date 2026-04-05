from __future__ import annotations

from fastapi import APIRouter

from .auth_account_routes import router as auth_account_router
from .auth_session_routes import router as auth_session_router
from .auth_token_routes import router as auth_token_router

router = APIRouter()
router.include_router(auth_account_router)
router.include_router(auth_session_router)
router.include_router(auth_token_router)
