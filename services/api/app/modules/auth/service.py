"""
Auth service — business logic for registration, login, and token refresh.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import UserRole
from app.core.exceptions import ConflictException, ForbiddenException, UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UserRepository(db)

    def _build_token_response(self, user: User) -> TokenResponse:
        extra = {"role": user.role, "hospital_id": str(user.hospital_id) if user.hospital_id else None}
        access_token = create_access_token(str(user.id), extra=extra)
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    # Roles that can be self-registered via the public endpoint
    _PUBLIC_ROLES: frozenset[UserRole] = frozenset({UserRole.PATIENT})

    # Roles that require an existing SUPER_ADMIN to grant
    _SUPER_ADMIN_ONLY_ROLES: frozenset[UserRole] = frozenset({
        UserRole.SUPER_ADMIN,
        UserRole.HOSPITAL_ADMIN,
    })

    def validate_role_assignment(
        self,
        requested_role: UserRole,
        actor: "User | None",  # type: ignore[name-defined]
    ) -> None:
        """
        Enforce who can assign which roles.

        - Public (actor=None): PATIENT only.
        - HOSPITAL_ADMIN:      RECEPTIONIST, DOCTOR.
        - SUPER_ADMIN:         any role.
        """
        if requested_role in self._PUBLIC_ROLES:
            return  # always allowed

        if actor is None:
            raise ForbiddenException(
                f"Role '{requested_role.value}' cannot be self-assigned. "
                "Contact your hospital administrator."
            )

        if requested_role in self._SUPER_ADMIN_ONLY_ROLES:
            if actor.role != UserRole.SUPER_ADMIN:
                raise ForbiddenException(
                    f"Only SUPER_ADMIN can grant the '{requested_role.value}' role."
                )
            return

        # RECEPTIONIST / DOCTOR — requires at least HOSPITAL_ADMIN
        allowed_granters = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}
        if actor.role not in allowed_granters:
            raise ForbiddenException(
                f"Role '{requested_role.value}' can only be granted by a HOSPITAL_ADMIN or SUPER_ADMIN."
            )

    async def register(
        self,
        payload: RegisterRequest,
        actor: "User | None" = None,  # type: ignore[name-defined]
    ) -> TokenResponse:
        """
        Register a new user.

        `actor` is the currently authenticated user performing the registration.
        Pass None for public (unauthenticated) self-registration.
        """
        self.validate_role_assignment(payload.role, actor)

        existing = await self._repo.get_by_email(payload.email)
        if existing:
            raise ConflictException("An account with this email already exists")

        user = await self._repo.create(
            email=payload.email.lower(),
            full_name=payload.full_name,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            role=payload.role,
            hospital_id=payload.hospital_id,
            is_active=True,
        )

        logger.info(
            "user_registered",
            user_id=str(user.id),
            role=user.role,
            actor_id=str(actor.id) if actor else "public",
        )
        return self._build_token_response(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self._repo.get_by_email(payload.email)

        # Constant-time failure to prevent email enumeration
        dummy_hash = "$2b$12$placeholder_to_prevent_timing_attacks_xxxx"
        if user is None:
            verify_password(payload.password, dummy_hash)
            raise UnauthorizedException("Invalid email or password")

        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedException("Account is inactive")

        await self._repo.update_last_login(user.id)
        logger.info("user_login", user_id=str(user.id))
        return self._build_token_response(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        from jose import JWTError
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise UnauthorizedException("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Malformed token")

        user = await self._repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedException("User not found or inactive")

        return self._build_token_response(user)
