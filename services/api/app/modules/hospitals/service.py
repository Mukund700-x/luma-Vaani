"""
Hospital service — business logic, RBAC enforcement, and audit logging.
Only SUPER_ADMIN can create hospitals and change is_active.
HOSPITAL_ADMIN can update their own hospital's non-critical fields.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AuditActorType, UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.hospitals.models import Hospital
from app.modules.hospitals.repository import HospitalRepository
from app.modules.hospitals.schemas import (
    HospitalCreate,
    HospitalResponse,
    HospitalSummary,
    HospitalUpdate,
)

logger = structlog.get_logger(__name__)


class HospitalService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = HospitalRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_404(self, hospital_id: uuid.UUID) -> Hospital:
        hospital = await self._repo.get_by_id(hospital_id)
        if not hospital:
            raise NotFoundException("Hospital", str(hospital_id))
        return hospital

    async def _assert_slug_available(
        self, slug: str, exclude_id: uuid.UUID | None = None
    ) -> None:
        if await self._repo.slug_exists(slug, exclude_id=exclude_id):
            raise ConflictException(f"Hospital slug '{slug}' is already taken")

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_hospitals(
        self,
        *,
        actor: User,
        params: PageParams,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> Page[HospitalSummary]:
        """
        SUPER_ADMIN sees all hospitals (paginated + filterable).
        HOSPITAL_ADMIN sees only their own hospital.
        """
        if actor.role == UserRole.SUPER_ADMIN:
            items, total = await self._repo.list(
                search=search,
                is_active=is_active,
                limit=params.size,
                offset=params.offset,
            )
        else:
            # Non-super users get their own hospital only
            if actor.hospital_id is None:
                return Page.create([], 0, params)
            hospital = await self._repo.get_by_id(actor.hospital_id)
            items = [hospital] if hospital else []
            total = len(items)

        return Page.create(
            [HospitalSummary.model_validate(h) for h in items],
            total,
            params,
        )

    async def get_hospital(
        self,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> HospitalResponse:
        """Get a single hospital. Access validated by HospitalPathDep upstream."""
        hospital = await self._get_or_404(hospital_id)
        return HospitalResponse.model_validate(hospital)

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create_hospital(
        self,
        payload: HospitalCreate,
        actor: User,
    ) -> HospitalResponse:
        """Create a new hospital — SUPER_ADMIN only."""
        if actor.role != UserRole.SUPER_ADMIN:
            raise ForbiddenException("Only SUPER_ADMIN can create hospitals")

        await self._assert_slug_available(payload.slug)

        hospital = await self._repo.create(
            name=payload.name,
            slug=payload.slug,
            contact_email=str(payload.contact_email) if payload.contact_email else None,
            contact_phone=payload.contact_phone,
            address=payload.address,
            config=payload.config.model_dump(),
        )

        await self._audit.log(
            action="hospital.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital.id,
            resource_type="hospital",
            resource_id=str(hospital.id),
            after_state={"name": hospital.name, "slug": hospital.slug},
        )

        logger.info("hospital_created", hospital_id=str(hospital.id), slug=hospital.slug)
        return HospitalResponse.model_validate(hospital)

    async def update_hospital(
        self,
        hospital_id: uuid.UUID,
        payload: HospitalUpdate,
        actor: User,
    ) -> HospitalResponse:
        """
        Update hospital fields.
        - SUPER_ADMIN: can change anything including is_active.
        - HOSPITAL_ADMIN: can change name, contact, address, config (not is_active).
        """
        hospital = await self._get_or_404(hospital_id)

        # HOSPITAL_ADMIN cannot change is_active
        if actor.role == UserRole.HOSPITAL_ADMIN and payload.is_active is not None:
            raise ForbiddenException("HOSPITAL_ADMIN cannot change hospital active status")

        before = {
            "name": hospital.name,
            "is_active": hospital.is_active,
            "contact_email": hospital.contact_email,
        }

        fields: dict = {}
        if payload.name is not None:
            fields["name"] = payload.name
        if payload.contact_email is not None:
            fields["contact_email"] = str(payload.contact_email)
        if payload.contact_phone is not None:
            fields["contact_phone"] = payload.contact_phone
        if payload.address is not None:
            fields["address"] = payload.address
        if payload.config is not None:
            # Merge config — don't clobber keys the caller didn't touch
            merged = {**hospital.config, **payload.config.model_dump(exclude_none=True)}
            fields["config"] = merged
        if payload.is_active is not None and actor.role == UserRole.SUPER_ADMIN:
            fields["is_active"] = payload.is_active

        if not fields:
            return HospitalResponse.model_validate(hospital)

        updated = await self._repo.update(hospital_id, fields)

        await self._audit.log(
            action="hospital.update",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="hospital",
            resource_id=str(hospital_id),
            before_state=before,
            after_state=fields,
        )

        logger.info("hospital_updated", hospital_id=str(hospital_id))
        return HospitalResponse.model_validate(updated)
