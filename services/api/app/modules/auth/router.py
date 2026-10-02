"""
Auth API router — /api/v1/auth/*
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    # Optional: if a staff member is creating an account for another role,
    # they authenticate first. Public (patient) registration passes no token.
    actor: Annotated[User | None, Depends(lambda: None)] = None,
) -> TokenResponse:
    """
    Register a new account.

    - **Public / unauthenticated**: only PATIENT role is permitted.
    - **Authenticated HOSPITAL_ADMIN**: may register RECEPTIONIST and DOCTOR.
    - **Authenticated SUPER_ADMIN**: may register any role including HOSPITAL_ADMIN.
    """
    return await AuthService(db).register(payload, actor=actor)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate and return access + refresh tokens."""
    return await AuthService(db).login(payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    return await AuthService(db).refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
