"""
Doctor service — business logic, RBAC, department assignment, and audit logging.
"""

import uuid
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AuditActorType, DoctorStatus, UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.doctors.models import Doctor
from app.modules.doctors.repository import DoctorRepository
from app.modules.doctors.schemas import (
    DoctorCreate,
    DoctorResponse,
    DoctorSummary,
    DoctorUpdate,
)

logger = structlog.get_logger(__name__)

_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}


class DoctorService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = DoctorRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_404(self, doctor_id: uuid.UUID, hospital_id: uuid.UUID) -> Doctor:
        doctor = await self._repo.get_by_id(doctor_id, hospital_id)
        if not doctor:
            raise NotFoundException("Doctor", str(doctor_id))
        return doctor

    def _assert_admin(self, actor: User) -> None:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Only HOSPITAL_ADMIN or SUPER_ADMIN can manage doctors")

    @staticmethod
    def _fee_to_paise(fee_inr: Decimal | None) -> int | None:
        if fee_inr is None:
            return None
        return int(fee_inr * 100)

    @staticmethod
    def _build_summary(doctor: Doctor) -> DoctorSummary:
        return DoctorSummary(
            id=doctor.id,
            hospital_id=doctor.hospital_id,
            full_name=doctor.full_name,
            specialization=doctor.specialization,
            status=doctor.status,
            avatar_url=doctor.avatar_url,
            consultation_fee_inr=doctor.consultation_fee_inr,
            primary_department_id=doctor.primary_department_id,
            is_active=doctor.is_active,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_doctors(
        self,
        hospital_id: uuid.UUID,
        *,
        params: PageParams,
        search: str | None = None,
        department_id: uuid.UUID | None = None,
        status: DoctorStatus | None = None,
        is_active: bool | None = None,
    ) -> Page[DoctorSummary]:
        items, total = await self._repo.list(
            hospital_id,
            search=search,
            department_id=department_id,
            status=status.value if status else None,
            is_active=is_active,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create([self._build_summary(d) for d in items], total, params)

    async def get_doctor(
        self, doctor_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> DoctorResponse:
        doctor = await self._get_or_404(doctor_id, hospital_id)
        return DoctorResponse.from_orm_with_links(doctor)

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create_doctor(
        self,
        hospital_id: uuid.UUID,
        payload: DoctorCreate,
        actor: User,
    ) -> DoctorResponse:
        self._assert_admin(actor)

        # If linking to a user account, verify that user belongs to this hospital
        if payload.user_id:
            if not await self._repo.user_id_in_hospital(payload.user_id, hospital_id):
                raise ConflictException(
                    "The specified user_id does not belong to this hospital"
                )

        doctor = await self._repo.create(
            hospital_id,
            user_id=payload.user_id,
            full_name=payload.full_name,
            registration_number=payload.registration_number,
            specialization=payload.specialization,
            qualifications=payload.qualifications,
            consultation_fee_paise=self._fee_to_paise(payload.consultation_fee_inr),
            bio=payload.bio,
            avatar_url=payload.avatar_url,
            status=DoctorStatus.ACTIVE,
            is_active=True,
        )

        if payload.departments:
            await self._repo.set_department_links(
                doctor.id,
                [
                    {"department_id": a.department_id, "is_primary": a.is_primary}
                    for a in payload.departments
                ],
            )
            # Reload to get fresh links
            doctor = await self._get_or_404(doctor.id, hospital_id)

        await self._audit.log(
            action="doctor.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor",
            resource_id=str(doctor.id),
            after_state={
                "full_name": doctor.full_name,
                "specialization": doctor.specialization,
                "department_count": len(doctor.department_links),
            },
        )
        logger.info("doctor_created", doctor_id=str(doctor.id), hospital_id=str(hospital_id))
        return DoctorResponse.from_orm_with_links(doctor)

    async def update_doctor(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: DoctorUpdate,
        actor: User,
    ) -> DoctorResponse:
        self._assert_admin(actor)
        doctor = await self._get_or_404(doctor_id, hospital_id)

        before = {
            "full_name": doctor.full_name,
            "status": doctor.status,
            "is_active": doctor.is_active,
        }

        fields: dict = {}
        if payload.full_name is not None:
            fields["full_name"] = payload.full_name
        if payload.registration_number is not None:
            fields["registration_number"] = payload.registration_number
        if payload.specialization is not None:
            fields["specialization"] = payload.specialization
        if payload.qualifications is not None:
            fields["qualifications"] = payload.qualifications
        if payload.consultation_fee_inr is not None:
            fields["consultation_fee_paise"] = self._fee_to_paise(payload.consultation_fee_inr)
        if payload.bio is not None:
            fields["bio"] = payload.bio
        if payload.avatar_url is not None:
            fields["avatar_url"] = payload.avatar_url
        if payload.status is not None:
            fields["status"] = payload.status
        if payload.is_active is not None:
            fields["is_active"] = payload.is_active

        if fields:
            doctor = await self._repo.update(doctor_id, hospital_id, fields)  # type: ignore[assignment]

        if payload.departments is not None:
            await self._repo.set_department_links(
                doctor_id,
                [
                    {"department_id": a.department_id, "is_primary": a.is_primary}
                    for a in payload.departments
                ],
            )

        # Reload fresh copy with updated links
        doctor = await self._get_or_404(doctor_id, hospital_id)

        await self._audit.log(
            action="doctor.update",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor",
            resource_id=str(doctor_id),
            before_state=before,
            after_state={k: str(v) for k, v in fields.items()},
        )
        logger.info("doctor_updated", doctor_id=str(doctor_id))
        return DoctorResponse.from_orm_with_links(doctor)

    async def deactivate_doctor(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        self._assert_admin(actor)
        doctor = await self._get_or_404(doctor_id, hospital_id)

        await self._repo.update(
            doctor_id, hospital_id, {"is_active": False, "status": DoctorStatus.INACTIVE}
        )

        await self._audit.log(
            action="doctor.deactivate",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor",
            resource_id=str(doctor_id),
            before_state={"full_name": doctor.full_name, "is_active": True},
        )
        logger.info("doctor_deactivated", doctor_id=str(doctor_id))
