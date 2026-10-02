"""
FastAPI dependencies: authentication, RBAC, and tenant-isolation guards.

Key exports:
- CurrentUser             — resolves the authenticated User ORM object
- require_roles(...)      — RBAC dependency factory
- HospitalPathDep         — validates hospital_id path param against current user's tenant
"""

import uuid
from collections.abc import Callable
from typing import Annotated

import structlog
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import decode_token
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository

logger = structlog.get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


# ── Core auth dependency ───────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Decode JWT, look up user, and return the User ORM object.
    Raises UnauthorizedException on any failure.
    """
    if not credentials:
        raise UnauthorizedException()

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise UnauthorizedException("Invalid or expired token")

    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Token missing subject")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("Account is inactive")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ── RBAC ──────────────────────────────────────────────────────────────────────

def require_roles(*roles: UserRole) -> Callable:
    """
    Dependency factory that enforces role-based access control.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))])
    """

    async def _check(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            logger.warning(
                "rbac_denied",
                user_id=str(current_user.id),
                required_roles=[r.value for r in roles],
                user_role=current_user.role.value,
            )
            raise ForbiddenException(
                f"Required role(s): {', '.join(r.value for r in roles)}"
            )
        return current_user

    return _check


# ── Tenant guard ───────────────────────────────────────────────────────────────

async def _verify_hospital_access(
    hospital_id: uuid.UUID,
    current_user: CurrentUser,
) -> uuid.UUID:
    """
    Validates that the authenticated user belongs to the hospital in the path.
    SUPER_ADMIN bypasses the check (can access all hospitals).

    Raises ForbiddenException if the user is trying to access a different hospital.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return hospital_id

    if current_user.hospital_id is None or current_user.hospital_id != hospital_id:
        logger.warning(
            "tenant_violation_attempt",
            user_id=str(current_user.id),
            user_hospital_id=str(current_user.hospital_id),
            requested_hospital_id=str(hospital_id),
        )
        raise ForbiddenException("Access to this hospital is not authorized")

    return hospital_id


HospitalPathDep = Annotated[uuid.UUID, Depends(_verify_hospital_access)]

