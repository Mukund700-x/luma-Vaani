"""
Appointment service — transactional booking, cancellation, and rescheduling.

BOOKING SAFETY MODEL:
    1. AvailabilityEngine.validate_slot() checks availability (soft check)
    2. Appointment is inserted
    3. DB partial unique index on (doctor_id, scheduled_at) WHERE status
       NOT IN ('CANCELLED', 'RESCHEDULED') catches any race conditions
    4. IntegrityError is caught and surfaced as ConflictException

PHI SAFETY:
    chief_complaint and notes are NEVER written to audit logs.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AppointmentStatus, AppointmentType, AuditActorType, UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import AppointmentRepository
from app.modules.appointments.schemas import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AppointmentSummary,
)
from app.modules.auth.models import User
from app.modules.departments.repository import DepartmentRepository
from app.modules.doctors.repository import DoctorRepository
from app.modules.hospitals.repository import HospitalRepository
from app.modules.patients.repository import PatientRepository
from app.modules.schedules.engine import AvailabilityEngine
from app.modules.schedules.repository import ScheduleRepository

logger = structlog.get_logger(__name__)

# Statuses that can be cancelled
_CANCELLABLE = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}
# Statuses that can be rescheduled
_RESCHEDULABLE = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}

# Roles allowed to book on behalf of a patient
_BOOKING_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.HOSPITAL_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
    UserRole.PATIENT,
}


class AppointmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AppointmentRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_404(
        self, appointment_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Appointment:
        apt = await self._repo.get_by_id(appointment_id, hospital_id)
        if not apt:
            raise NotFoundException("Appointment", str(appointment_id))
        return apt

    async def _get_hospital_timezone(self, hospital_id: uuid.UUID) -> str:
        hospital = await HospitalRepository(self._db).get_by_id(hospital_id)
        if hospital and isinstance(hospital.config, dict):
            return hospital.config.get("timezone", "Asia/Kolkata")
        return "Asia/Kolkata"

    async def _get_cancellation_cutoff_hours(self, hospital_id: uuid.UUID) -> int:
        hospital = await HospitalRepository(self._db).get_by_id(hospital_id)
        if hospital and isinstance(hospital.config, dict):
            return hospital.config.get("cancellation_cutoff_hours", 2)
        return 2

    def _build_engine(self) -> AvailabilityEngine:
        return AvailabilityEngine(
            schedule_repo=ScheduleRepository(self._db),
            appointment_repo=self._repo,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_appointments(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        *,
        params: PageParams,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        status: AppointmentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Page[AppointmentSummary]:
        if actor.role not in _BOOKING_ROLES:
            raise ForbiddenException("Access denied")

        items, total = await self._repo.list(
            hospital_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=department_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [AppointmentSummary.model_validate(a) for a in items],
            total,
            params,
        )

    async def get_appointment(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> AppointmentResponse:
        if actor.role not in _BOOKING_ROLES:
            raise ForbiddenException("Access denied")
        apt = await self._get_or_404(appointment_id, hospital_id)
        return AppointmentResponse.model_validate(apt)

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_appointment(
        self,
        hospital_id: uuid.UUID,
        payload: AppointmentCreate,
        actor: User,
    ) -> AppointmentResponse:
        if actor.role not in _BOOKING_ROLES:
            raise ForbiddenException("Access denied to book appointments")

        tz_name = await self._get_hospital_timezone(hospital_id)

        # ── 1. Verify all referenced entities exist in this hospital ──────────
        doctor = await DoctorRepository(self._db).get_by_id(
            payload.doctor_id, hospital_id
        )
        if not doctor or not doctor.is_active:
            raise NotFoundException("Doctor", str(payload.doctor_id))

        patient = await PatientRepository(self._db).get_by_id(
            payload.patient_id, hospital_id
        )
        if not patient or not patient.is_active:
            raise NotFoundException("Patient", str(payload.patient_id))

        department = await DepartmentRepository(self._db).get_by_id(
            payload.department_id, hospital_id
        )
        if not department or not department.is_active:
            raise NotFoundException("Department", str(payload.department_id))

        # ── 2. Validate the requested slot via the engine ─────────────────────
        engine = self._build_engine()
        is_valid, reason, duration_minutes = await engine.validate_slot(
            doctor_id=payload.doctor_id,
            hospital_id=hospital_id,
            scheduled_at=payload.scheduled_at,
            hospital_timezone=tz_name,
        )
        if not is_valid:
            raise ConflictException(reason)

        # Ensure UTC-aware
        scheduled_at_utc = (
            payload.scheduled_at.replace(tzinfo=UTC)
            if payload.scheduled_at.tzinfo is None
            else payload.scheduled_at.astimezone(UTC)
        )
        ends_at_utc = scheduled_at_utc + timedelta(minutes=duration_minutes)

        # ── 3. Create appointment (DB constraint is the final guard) ──────────
        try:
            apt = await self._repo.create(
                hospital_id,
                patient_id=payload.patient_id,
                doctor_id=payload.doctor_id,
                department_id=payload.department_id,
                scheduled_at=scheduled_at_utc,
                ends_at=ends_at_utc,
                duration_minutes=duration_minutes,
                status=AppointmentStatus.CONFIRMED,
                appointment_type=payload.appointment_type,
                source=payload.source,
                conversation_id=payload.conversation_id,
                notes=payload.notes,
                chief_complaint=payload.chief_complaint,
            )
        except IntegrityError:
            raise ConflictException(
                "This time slot was just booked by another request. "
                "Please select a different slot."
            )

        # ── 4. Audit (no PHI) ─────────────────────────────────────────────────
        await self._audit.log(
            action="appointment.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="appointment",
            resource_id=str(apt.id),
            after_state={
                "doctor_id": str(apt.doctor_id),
                "department_id": str(apt.department_id),
                "scheduled_at": apt.scheduled_at.isoformat(),
                "status": apt.status,
                "source": apt.source,
            },
        )

        logger.info(
            "appointment_created",
            appointment_id=str(apt.id),
            doctor_id=str(apt.doctor_id),
            scheduled_at=apt.scheduled_at.isoformat(),
            hospital_id=str(hospital_id),
            source=apt.source,
        )

        # ── Queue confirmation + reminder notifications (non-fatal) ──────────────────
        try:
            from app.modules.notifications.service import NotificationService
            await NotificationService(self._db).queue_for_appointment(
                appointment_id=apt.id,
                hospital_id=hospital_id,
                event_type="appointment.confirmed",
            )
        except Exception:
            logger.warning("notification_queue_failed", appointment_id=str(apt.id))

        return AppointmentResponse.model_validate(apt)

    # ── Cancel ────────────────────────────────────────────────────────────────

    async def cancel_appointment(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: AppointmentCancelRequest,
        actor: User,
    ) -> AppointmentResponse:
        apt = await self._get_or_404(appointment_id, hospital_id)

        if apt.status not in _CANCELLABLE:
            raise ConflictException(
                f"Cannot cancel an appointment with status '{apt.status}'. "
                f"Only {[s.value for s in _CANCELLABLE]} appointments can be cancelled."
            )

        # Enforce cancellation cutoff for non-admin users
        if actor.role not in {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.RECEPTIONIST}:
            cutoff_hours = await self._get_cancellation_cutoff_hours(hospital_id)
            hours_until = (apt.scheduled_at - datetime.now(UTC)).total_seconds() / 3600
            if hours_until < cutoff_hours:
                raise ConflictException(
                    f"Cancellations must be made at least {cutoff_hours} hour(s) "
                    f"before the appointment time."
                )

        now_utc = datetime.now(UTC)
        updated = await self._repo.update(
            appointment_id,
            hospital_id,
            {
                "status": AppointmentStatus.CANCELLED,
                "cancellation_reason": payload.reason,
                "cancelled_at": now_utc,
                "cancelled_by_user_id": actor.id,
            },
        )

        await self._audit.log(
            action="appointment.cancel",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="appointment",
            resource_id=str(appointment_id),
            before_state={"status": apt.status.value, "scheduled_at": apt.scheduled_at.isoformat()},
            after_state={"status": AppointmentStatus.CANCELLED.value},
        )
        logger.info("appointment_cancelled", appointment_id=str(appointment_id))
        return AppointmentResponse.model_validate(updated)

    # ── Reschedule ────────────────────────────────────────────────────────────

    async def reschedule_appointment(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: AppointmentRescheduleRequest,
        actor: User,
    ) -> AppointmentResponse:
        """
        Reschedule flow:
        1. Mark original appointment as RESCHEDULED
        2. Create a new appointment at the new time (runs full validation)
        3. Link the new appointment back via rescheduled_from_id

        If step 2 fails (slot taken), the original is NOT marked as rescheduled.
        This keeps the patient's existing booking intact.
        """
        original = await self._get_or_404(appointment_id, hospital_id)

        if original.status not in _RESCHEDULABLE:
            raise ConflictException(
                f"Cannot reschedule an appointment with status '{original.status}'."
            )

        tz_name = await self._get_hospital_timezone(hospital_id)
        engine = self._build_engine()

        is_valid, reason, duration_minutes = await engine.validate_slot(
            doctor_id=original.doctor_id,
            hospital_id=hospital_id,
            scheduled_at=payload.new_scheduled_at,
            hospital_timezone=tz_name,
        )
        if not is_valid:
            raise ConflictException(f"Requested slot is not available: {reason}")

        new_scheduled_utc = (
            payload.new_scheduled_at.replace(tzinfo=UTC)
            if payload.new_scheduled_at.tzinfo is None
            else payload.new_scheduled_at.astimezone(UTC)
        )
        new_ends_utc = new_scheduled_utc + timedelta(minutes=duration_minutes)

        # Mark original as rescheduled FIRST (releases the slot lock)
        await self._repo.update(
            appointment_id,
            hospital_id,
            {
                "status": AppointmentStatus.RESCHEDULED,
                "cancellation_reason": payload.reason,
                "cancelled_at": datetime.now(UTC),
                "cancelled_by_user_id": actor.id,
            },
        )

        try:
            new_apt = await self._repo.create(
                hospital_id,
                patient_id=original.patient_id,
                doctor_id=original.doctor_id,
                department_id=original.department_id,
                scheduled_at=new_scheduled_utc,
                ends_at=new_ends_utc,
                duration_minutes=duration_minutes,
                status=AppointmentStatus.CONFIRMED,
                appointment_type=original.appointment_type,
                source=original.source,
                conversation_id=original.conversation_id,
                notes=payload.reason,
                rescheduled_from_id=appointment_id,
            )
        except IntegrityError:
            # Rollback the status change — restore original
            await self._repo.update(
                appointment_id,
                hospital_id,
                {
                    "status": AppointmentStatus.CONFIRMED,
                    "cancellation_reason": None,
                    "cancelled_at": None,
                    "cancelled_by_user_id": None,
                },
            )
            raise ConflictException(
                "The new slot was just taken. Your original appointment is unchanged."
            )

        await self._audit.log(
            action="appointment.reschedule",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="appointment",
            resource_id=str(new_apt.id),
            before_state={"original_id": str(appointment_id), "scheduled_at": original.scheduled_at.isoformat()},
            after_state={"new_id": str(new_apt.id), "new_scheduled_at": new_scheduled_utc.isoformat()},
        )
        logger.info(
            "appointment_rescheduled",
            original_id=str(appointment_id),
            new_id=str(new_apt.id),
        )
        return AppointmentResponse.model_validate(new_apt)

    # ── Admin status update ───────────────────────────────────────────────────

    async def update_status(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        new_status: AppointmentStatus,
        actor: User,
    ) -> AppointmentResponse:
        """Mark appointment as COMPLETED or NO_SHOW. HOSPITAL_ADMIN+ only."""
        if actor.role not in {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.RECEPTIONIST, UserRole.DOCTOR}:
            raise ForbiddenException("Insufficient permissions to update appointment status")

        allowed_transitions = {
            AppointmentStatus.CONFIRMED: {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW},
        }
        apt = await self._get_or_404(appointment_id, hospital_id)
        allowed = allowed_transitions.get(apt.status, set())

        if new_status not in allowed:
            raise ConflictException(
                f"Cannot transition from '{apt.status}' to '{new_status}'. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        updated = await self._repo.update(
            appointment_id, hospital_id, {"status": new_status}
        )

        await self._audit.log(
            action=f"appointment.{new_status.value.lower()}",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="appointment",
            resource_id=str(appointment_id),
            before_state={"status": apt.status.value},
            after_state={"status": new_status.value},
        )
        return AppointmentResponse.model_validate(updated)
