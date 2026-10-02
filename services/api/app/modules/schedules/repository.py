"""
Schedule repository — tenant-scoped data access for doctor_schedules and schedule_exceptions.
Provides targeted query methods for the AvailabilityEngine.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ScheduleExceptionType
from app.modules.schedules.models import DoctorSchedule, ScheduleException


class ScheduleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── DoctorSchedule ─────────────────────────────────────────────────────────

    async def get_schedule_by_id(
        self, schedule_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> DoctorSchedule | None:
        result = await self._db.execute(
            select(DoctorSchedule).where(
                and_(
                    DoctorSchedule.id == schedule_id,
                    DoctorSchedule.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_schedules(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> list[DoctorSchedule]:
        q = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.hospital_id == hospital_id,
            )
        )
        if not include_inactive:
            q = q.where(DoctorSchedule.is_active == True)  # noqa: E712
        q = q.order_by(DoctorSchedule.day_of_week.asc(), DoctorSchedule.start_time.asc())
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def get_active_schedules_for_range(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> list[DoctorSchedule]:
        """
        Returns all active schedules valid during [date_from, date_to].
        Handles valid_from / valid_until bounds.
        """
        q = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.hospital_id == hospital_id,
                DoctorSchedule.is_active == True,  # noqa: E712
                # Schedule not yet expired
                (DoctorSchedule.valid_until == None)  # noqa: E711
                | (DoctorSchedule.valid_until >= date_from),
                # Schedule already started
                (DoctorSchedule.valid_from == None)  # noqa: E711
                | (DoctorSchedule.valid_from <= date_to),
            )
        )
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def create_schedule(
        self, hospital_id: uuid.UUID, doctor_id: uuid.UUID, **fields: Any
    ) -> DoctorSchedule:
        schedule = DoctorSchedule(
            hospital_id=hospital_id, doctor_id=doctor_id, **fields
        )
        self._db.add(schedule)
        await self._db.flush()
        await self._db.refresh(schedule)
        return schedule

    async def update_schedule(
        self,
        schedule_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> DoctorSchedule | None:
        await self._db.execute(
            update(DoctorSchedule)
            .where(
                and_(
                    DoctorSchedule.id == schedule_id,
                    DoctorSchedule.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_schedule_by_id(schedule_id, hospital_id)

    # ── ScheduleException ──────────────────────────────────────────────────────

    async def get_exception_by_id(
        self, exception_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> ScheduleException | None:
        result = await self._db.execute(
            select(ScheduleException).where(
                and_(
                    ScheduleException.id == exception_id,
                    ScheduleException.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_exceptions(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        *,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> list[ScheduleException]:
        q = select(ScheduleException).where(
            and_(
                ScheduleException.doctor_id == doctor_id,
                ScheduleException.hospital_id == hospital_id,
            )
        )
        if from_dt:
            q = q.where(ScheduleException.end_datetime >= from_dt)
        if to_dt:
            q = q.where(ScheduleException.start_datetime <= to_dt)
        q = q.order_by(ScheduleException.start_datetime.asc())
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def get_exceptions_in_range(
        self,
        doctor_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> list[ScheduleException]:
        """
        Returns all exceptions that OVERLAP with [range_start, range_end].
        Used by the AvailabilityEngine during slot filtering.

        An exception overlaps if: exception.start < range_end AND exception.end > range_start
        """
        q = select(ScheduleException).where(
            and_(
                ScheduleException.doctor_id == doctor_id,
                ScheduleException.start_datetime < range_end,
                ScheduleException.end_datetime > range_start,
                # Only blocking types affect availability
                ScheduleException.exception_type.in_([
                    ScheduleExceptionType.LEAVE.value,
                    ScheduleExceptionType.HOLIDAY.value,
                    ScheduleExceptionType.BLOCKED.value,
                ]),
            )
        )
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def create_exception(
        self,
        hospital_id: uuid.UUID,
        doctor_id: uuid.UUID,
        created_by: uuid.UUID | None,
        **fields: Any,
    ) -> ScheduleException:
        exc = ScheduleException(
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            created_by=created_by,
            **fields,
        )
        self._db.add(exc)
        await self._db.flush()
        await self._db.refresh(exc)
        return exc

    async def delete_exception(
        self, exception_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> bool:
        result = await self._db.execute(
            delete(ScheduleException).where(
                and_(
                    ScheduleException.id == exception_id,
                    ScheduleException.hospital_id == hospital_id,
                )
            )
        )
        return result.rowcount > 0  # type: ignore[return-value]

    async def get_slot_duration_for_datetime(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        target_date: date,
        wall_clock_time: "time",  # type: ignore[name-defined]
    ) -> int | None:
        """
        Find the slot duration for a given doctor at a given local time.
        Returns None if no matching schedule found.
        """
        from datetime import time as _time  # avoid circular
        q = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.hospital_id == hospital_id,
                DoctorSchedule.is_active == True,  # noqa: E712
                DoctorSchedule.day_of_week == target_date.weekday(),
                DoctorSchedule.start_time <= wall_clock_time,
                DoctorSchedule.end_time > wall_clock_time,
                (DoctorSchedule.valid_from == None)  # noqa: E711
                | (DoctorSchedule.valid_from <= target_date),
                (DoctorSchedule.valid_until == None)  # noqa: E711
                | (DoctorSchedule.valid_until >= target_date),
            )
        ).limit(1)
        result = await self._db.execute(q)
        schedule = result.scalar_one_or_none()
        return schedule.slot_duration_minutes if schedule else None
