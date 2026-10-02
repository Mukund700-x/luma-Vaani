"""
Schedule service — manages DoctorSchedule and ScheduleException records
and exposes the AvailabilityEngine for the API layer.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AuditActorType, UserRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.doctors.repository import DoctorRepository
from app.modules.hospitals.repository import HospitalRepository
from app.modules.schedules.engine import AvailabilityEngine, AvailableSlotInternal
from app.modules.schedules.models import DoctorSchedule, ScheduleException
from app.modules.schedules.repository import ScheduleRepository
from app.modules.schedules.schemas import (
    AvailableSlot,
    DoctorAvailabilityResponse,
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    DoctorScheduleUpdate,
    ScheduleExceptionCreate,
    ScheduleExceptionResponse,
)

from datetime import date

logger = structlog.get_logger(__name__)

_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}


class ScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ScheduleRepository(db)
        self._audit = AuditService(db)

    def _assert_admin(self, actor: User) -> None:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Only HOSPITAL_ADMIN or SUPER_ADMIN can manage schedules")

    async def _get_schedule_or_404(
        self, schedule_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> DoctorSchedule:
        s = await self._repo.get_schedule_by_id(schedule_id, hospital_id)
        if not s:
            raise NotFoundException("DoctorSchedule", str(schedule_id))
        return s

    async def _get_exception_or_404(
        self, exception_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> ScheduleException:
        e = await self._repo.get_exception_by_id(exception_id, hospital_id)
        if not e:
            raise NotFoundException("ScheduleException", str(exception_id))
        return e

    async def _verify_doctor(
        self, doctor_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> None:
        """Verify the doctor exists in this hospital."""
        doc = await DoctorRepository(self._db).get_by_id(doctor_id, hospital_id)
        if not doc:
            raise NotFoundException("Doctor", str(doctor_id))

    async def _get_hospital_timezone(self, hospital_id: uuid.UUID) -> str:
        hospital = await HospitalRepository(self._db).get_by_id(hospital_id)
        if hospital and isinstance(hospital.config, dict):
            return hospital.config.get("timezone", "Asia/Kolkata")
        return "Asia/Kolkata"

    # ── Doctor Schedules ───────────────────────────────────────────────────────

    async def list_schedules(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[DoctorScheduleResponse]:
        await self._verify_doctor(doctor_id, hospital_id)
        schedules = await self._repo.list_schedules(
            doctor_id, hospital_id, include_inactive=include_inactive
        )
        return [DoctorScheduleResponse.from_orm(s) for s in schedules]

    async def create_schedule(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: DoctorScheduleCreate,
        actor: User,
    ) -> DoctorScheduleResponse:
        self._assert_admin(actor)
        await self._verify_doctor(doctor_id, hospital_id)

        schedule = await self._repo.create_schedule(
            hospital_id,
            doctor_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            slot_duration_minutes=payload.slot_duration_minutes,
            max_appointments=payload.max_appointments,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            is_active=True,
        )

        await self._audit.log(
            action="schedule.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor_schedule",
            resource_id=str(schedule.id),
            after_state={
                "doctor_id": str(doctor_id),
                "day_of_week": schedule.day_of_week,
                "start_time": str(schedule.start_time),
                "end_time": str(schedule.end_time),
            },
        )
        logger.info("schedule_created", schedule_id=str(schedule.id), doctor_id=str(doctor_id))
        return DoctorScheduleResponse.from_orm(schedule)

    async def update_schedule(
        self,
        schedule_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: DoctorScheduleUpdate,
        actor: User,
    ) -> DoctorScheduleResponse:
        self._assert_admin(actor)
        schedule = await self._get_schedule_or_404(schedule_id, hospital_id)

        fields: dict = {}
        if payload.start_time is not None:
            fields["start_time"] = payload.start_time
        if payload.end_time is not None:
            fields["end_time"] = payload.end_time
        if payload.slot_duration_minutes is not None:
            fields["slot_duration_minutes"] = payload.slot_duration_minutes
        if payload.max_appointments is not None:
            fields["max_appointments"] = payload.max_appointments
        if payload.is_active is not None:
            fields["is_active"] = payload.is_active
        if payload.valid_from is not None:
            fields["valid_from"] = payload.valid_from
        if payload.valid_until is not None:
            fields["valid_until"] = payload.valid_until

        if not fields:
            return DoctorScheduleResponse.from_orm(schedule)

        updated = await self._repo.update_schedule(schedule_id, hospital_id, fields)

        await self._audit.log(
            action="schedule.update",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor_schedule",
            resource_id=str(schedule_id),
            before_state={"is_active": schedule.is_active},
            after_state={k: str(v) for k, v in fields.items()},
        )
        return DoctorScheduleResponse.from_orm(updated)

    async def delete_schedule(
        self,
        schedule_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        """Soft-delete: deactivates the schedule."""
        self._assert_admin(actor)
        await self._get_schedule_or_404(schedule_id, hospital_id)
        await self._repo.update_schedule(schedule_id, hospital_id, {"is_active": False})

        await self._audit.log(
            action="schedule.deactivate",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="doctor_schedule",
            resource_id=str(schedule_id),
        )

    # ── Schedule Exceptions ────────────────────────────────────────────────────

    async def list_exceptions(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> list[ScheduleExceptionResponse]:
        await self._verify_doctor(doctor_id, hospital_id)
        exceptions = await self._repo.list_exceptions(
            doctor_id, hospital_id, from_dt=from_dt, to_dt=to_dt
        )
        return [ScheduleExceptionResponse.model_validate(e) for e in exceptions]

    async def create_exception(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: ScheduleExceptionCreate,
        actor: User,
    ) -> ScheduleExceptionResponse:
        self._assert_admin(actor)
        await self._verify_doctor(doctor_id, hospital_id)

        exc = await self._repo.create_exception(
            hospital_id,
            doctor_id,
            created_by=actor.id,
            exception_type=payload.exception_type,
            start_datetime=payload.start_datetime,
            end_datetime=payload.end_datetime,
            reason=payload.reason,
            is_all_day=payload.is_all_day,
        )

        await self._audit.log(
            action="schedule_exception.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="schedule_exception",
            resource_id=str(exc.id),
            after_state={
                "doctor_id": str(doctor_id),
                "exception_type": exc.exception_type.value,
                "start": str(exc.start_datetime),
                "end": str(exc.end_datetime),
            },
        )
        logger.info("schedule_exception_created", exc_id=str(exc.id), doctor_id=str(doctor_id))
        return ScheduleExceptionResponse.model_validate(exc)

    async def delete_exception(
        self,
        exception_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        """Hard-delete: exceptions are immutable, remove and recreate if needed."""
        self._assert_admin(actor)
        exc = await self._get_exception_or_404(exception_id, hospital_id)
        deleted = await self._repo.delete_exception(exception_id, hospital_id)
        if not deleted:
            raise NotFoundException("ScheduleException", str(exception_id))

        await self._audit.log(
            action="schedule_exception.delete",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="schedule_exception",
            resource_id=str(exception_id),
            before_state={"exception_type": exc.exception_type.value},
        )

    # ── Availability (Engine facade) ───────────────────────────────────────────

    async def get_availability(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        date_from: date,
        date_to: date,
        primary_department_id: uuid.UUID | None = None,
    ) -> DoctorAvailabilityResponse:
        """
        Returns all available slots for a doctor over a date range.
        This is the primary entry point for both the API and AI tool layer.
        """
        await self._verify_doctor(doctor_id, hospital_id)
        tz_name = await self._get_hospital_timezone(hospital_id)

        from app.modules.appointments.repository import AppointmentRepository
        engine = AvailabilityEngine(
            schedule_repo=self._repo,
            appointment_repo=AppointmentRepository(self._db),
        )

        internal_slots = await engine.get_available_slots(
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            date_from=date_from,
            date_to=date_to,
            hospital_timezone=tz_name,
            primary_department_id=primary_department_id,
        )

        api_slots = [
            AvailableSlot(
                scheduled_at=s.scheduled_at,
                ends_at=s.ends_at,
                duration_minutes=s.duration_minutes,
                doctor_id=s.doctor_id,
                hospital_id=s.hospital_id,
                slot_key=s.scheduled_at.isoformat(),
            )
            for s in internal_slots
        ]

        return DoctorAvailabilityResponse(
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            date_from=date_from,
            date_to=date_to,
            timezone=tz_name,
            total_slots=len(api_slots),
            slots=api_slots,
        )
