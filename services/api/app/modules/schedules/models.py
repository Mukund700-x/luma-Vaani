"""
DoctorSchedule and ScheduleException ORM models.

DoctorSchedule: defines recurring weekly availability for a doctor.
ScheduleException: one-time override — leave, holiday, partial block, or extended hours.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import ScheduleExceptionType


class DoctorSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Recurring weekly availability window for a doctor.
    Each record represents one day-of-week block (e.g., Monday 09:00–13:00).
    Multiple records can exist for the same day (e.g., two separate morning and afternoon blocks).

    Times are stored as wall-clock time (TIME) without timezone.
    The hospital config timezone is applied at runtime by the AvailabilityEngine.
    """

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        Index("ix_doctor_schedules_doctor_id", "doctor_id"),
        Index("ix_doctor_schedules_hospital_id", "hospital_id"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 0 = Monday … 6 = Sunday (Python weekday() convention)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Wall-clock local time — engine applies hospital timezone
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Appointment slot length in minutes for this schedule block
    slot_duration_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=20
    )
    # Maximum appointments allowed in this block per day; None = unlimited
    max_appointments: Mapped[int | None] = mapped_column(SmallInteger)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Optional date range — schedule only applies between these dates
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", lazy="select")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return (
            f"<DoctorSchedule id={self.id} doctor={self.doctor_id} "
            f"day={days[self.day_of_week]} {self.start_time}–{self.end_time}>"
        )


class ScheduleException(Base, UUIDPrimaryKeyMixin):
    """
    One-time override to a doctor's recurring schedule.

    Types:
    - LEAVE:    Doctor is on planned leave (full or partial day)
    - HOLIDAY:  Hospital holiday — doctor is unavailable
    - BLOCKED:  Admin-blocked period (non-clinical reason)
    - EXTENDED: Doctor has additional availability outside normal schedule

    start_datetime / end_datetime are UTC TIMESTAMPTZ.
    The engine compares these against generated slot times (also UTC).
    """

    __tablename__ = "schedule_exceptions"
    __table_args__ = (
        Index("ix_schedule_exceptions_doctor_id", "doctor_id"),
        Index(
            "ix_schedule_exceptions_doctor_range",
            "doctor_id",
            "start_datetime",
            "end_datetime",
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )

    exception_type: Mapped[ScheduleExceptionType] = mapped_column(
        String(20), nullable=False
    )

    # UTC datetimes
    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    reason: Mapped[str | None] = mapped_column(Text)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleException id={self.id} type={self.exception_type} "
            f"doctor={self.doctor_id} {self.start_datetime}–{self.end_datetime}>"
        )
