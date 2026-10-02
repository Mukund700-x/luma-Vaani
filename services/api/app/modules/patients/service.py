"""
Patient service — business logic, RBAC, MRN management, and PHI-safe audit logging.

PHI SAFETY RULE:
    Audit logs must NEVER contain patient full_name, phone, email, DoB, or
    any other PHI. Only patient_id is recorded in audit records.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AuditActorType, UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.patients.models import Patient
from app.modules.patients.repository import PatientRepository
from app.modules.patients.schemas import (
    PatientCreate,
    PatientResponse,
    PatientSummary,
    PatientUpdate,
)

logger = structlog.get_logger(__name__)

# Staff roles that can manage patients
_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.HOSPITAL_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
}


class PatientService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PatientRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_404(
        self, patient_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Patient:
        patient = await self._repo.get_by_id(patient_id, hospital_id)
        if not patient:
            raise NotFoundException("Patient", str(patient_id))
        return patient

    def _assert_staff(self, actor: User) -> None:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Access to patient records requires staff authorization")

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_patients(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        *,
        params: PageParams,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> Page[PatientSummary]:
        self._assert_staff(actor)

        items, total = await self._repo.list(
            hospital_id,
            search=search,
            is_active=is_active,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [PatientSummary.model_validate(p) for p in items],
            total,
            params,
        )

    async def get_patient(
        self,
        patient_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> PatientResponse:
        self._assert_staff(actor)
        patient = await self._get_or_404(patient_id, hospital_id)
        return PatientResponse.model_validate(patient)

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create_patient(
        self,
        hospital_id: uuid.UUID,
        payload: PatientCreate,
        actor: User,
    ) -> PatientResponse:
        self._assert_staff(actor)

        # MRN uniqueness check
        if payload.mrn:
            if await self._repo.mrn_exists(payload.mrn, hospital_id):
                raise ConflictException(
                    f"MRN '{payload.mrn}' is already registered in this hospital"
                )

        patient = await self._repo.create(
            hospital_id,
            mrn=payload.mrn,
            full_name=payload.full_name,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender.value if payload.gender else None,
            blood_group=payload.blood_group.value if payload.blood_group else None,
            preferred_language=payload.preferred_language,
            emergency_contact=payload.emergency_contact.model_dump(exclude_none=True),
            address=payload.address.model_dump(exclude_none=True) if payload.address else None,
        )

        # AUDIT: Only log patient_id — NO PHI
        await self._audit.log(
            action="patient.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="patient",
            resource_id=str(patient.id),
            # No before_state/after_state — would contain PHI
            metadata={"has_mrn": payload.mrn is not None},
        )
        logger.info("patient_created", patient_id=str(patient.id), hospital_id=str(hospital_id))
        return PatientResponse.model_validate(patient)

    async def update_patient(
        self,
        patient_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: PatientUpdate,
        actor: User,
    ) -> PatientResponse:
        self._assert_staff(actor)
        await self._get_or_404(patient_id, hospital_id)

        fields: dict = {}
        if payload.full_name is not None:
            fields["full_name"] = payload.full_name
        if payload.phone is not None:
            fields["phone"] = payload.phone
        if payload.email is not None:
            fields["email"] = str(payload.email)
        if payload.date_of_birth is not None:
            fields["date_of_birth"] = payload.date_of_birth
        if payload.gender is not None:
            fields["gender"] = payload.gender.value
        if payload.blood_group is not None:
            fields["blood_group"] = payload.blood_group.value
        if payload.preferred_language is not None:
            fields["preferred_language"] = payload.preferred_language
        if payload.emergency_contact is not None:
            fields["emergency_contact"] = payload.emergency_contact.model_dump(exclude_none=True)
        if payload.address is not None:
            fields["address"] = payload.address.model_dump(exclude_none=True)
        if payload.is_active is not None:
            # Only admins can deactivate patients
            if actor.role not in {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}:
                raise ForbiddenException("Only admins can change patient active status")
            fields["is_active"] = payload.is_active

        if not fields:
            patient = await self._get_or_404(patient_id, hospital_id)
            return PatientResponse.model_validate(patient)

        updated = await self._repo.update(patient_id, hospital_id, fields)

        # AUDIT: No PHI in state diffs
        await self._audit.log(
            action="patient.update",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="patient",
            resource_id=str(patient_id),
            metadata={"updated_fields": [k for k in fields if k not in {"full_name", "phone", "email", "date_of_birth"}]},
        )
        logger.info("patient_updated", patient_id=str(patient_id))
        return PatientResponse.model_validate(updated)
