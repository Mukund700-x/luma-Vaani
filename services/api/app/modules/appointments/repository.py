"""
Appointment repository — tenant-scoped data access.

Provides the booked slot queries consumed by the AvailabilityEngine.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AppointmentStatus
from app.modules.appointments.models import Appointment

# Statuses that "occupy" a slot — cancelled/rescheduled do NOT block availability
_ACTIVE_STATUSES = (
    AppointmentStatus.PENDING.value,
    AppointmentStatus.CONFIRMED.value,
    AppointmentStatus.COMPLETED.value,
    AppointmentStatus.NO_SHOW.value,
)


class AppointmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Engine queries (performance-critical) ──────────────────────────────────

    async def get_booked_datetimes(
        self,
        doctor_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> set[datetime]:
        """
        Returns the set of scheduled_at UTC datetimes for active appointments
        in the given range. Used by AvailabilityEngine to filter occupied slots.

        Only active statuses are considered (PENDING, CONFIRMED, COMPLETED, NO_SHOW).
        CANCELLED and RESCHEDULED do NOT block the slot.
        """
        q = select(Appointment.scheduled_at).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at >= range_start,
                Appointment.scheduled_at < range_end,
                Appointment.status.in_(_ACTIVE_STATUSES),
            )
        )
        result = await self._db.execute(q)
        return set(result.scalars().all())

    async def is_slot_taken(
        self, doctor_id: uuid.UUID, scheduled_at: datetime
    ) -> bool:
        """Point check: is a specific slot already booked? Used in validate_slot."""
        q = select(func.count()).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at == scheduled_at,
                Appointment.status.in_(_ACTIVE_STATUSES),
            )
        )
        result = await self._db.execute(q)
        return (result.scalar_one() or 0) > 0

    # ── Standard CRUD ─────────────────────────────────────────────────────────

    async def get_by_id(
        self, appointment_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Appointment | None:
        result = await self._db.execute(
            select(Appointment).where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        status: AppointmentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Appointment], int]:
        base_q = select(Appointment).where(Appointment.hospital_id == hospital_id)

        if patient_id:
            base_q = base_q.where(Appointment.patient_id == patient_id)
        if doctor_id:
            base_q = base_q.where(Appointment.doctor_id == doctor_id)
        if department_id:
            base_q = base_q.where(Appointment.department_id == department_id)
        if status:
            base_q = base_q.where(Appointment.status == status.value)
        if date_from:
            base_q = base_q.where(Appointment.scheduled_at >= date_from)
        if date_to:
            base_q = base_q.where(Appointment.scheduled_at <= date_to)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()

        items_q = (
            base_q.order_by(Appointment.scheduled_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._db.execute(items_q)).scalars().all())
        return items, total

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> Appointment:
        """
        Create an appointment.
        Caller must catch sqlalchemy.exc.IntegrityError for double-booking violations.
        """
        apt = Appointment(hospital_id=hospital_id, **fields)
        self._db.add(apt)
        await self._db.flush()
        await self._db.refresh(apt)
        return apt

    async def update(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Appointment | None:
        await self._db.execute(
            update(Appointment)
            .where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(appointment_id, hospital_id)
