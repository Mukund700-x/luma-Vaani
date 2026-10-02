"""
Schedules and Availability Pydantic schemas.
"""

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import ScheduleExceptionType

# 0 = Monday … 6 = Sunday
DayOfWeek = Literal[0, 1, 2, 3, 4, 5, 6]

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── DoctorSchedule schemas ─────────────────────────────────────────────────────

class DoctorScheduleCreate(BaseModel):
    day_of_week: DayOfWeek = Field(description="0=Monday, 1=Tuesday … 6=Sunday")
    start_time: time = Field(description="Wall-clock start time in hospital local timezone")
    end_time: time = Field(description="Wall-clock end time in hospital local timezone")
    slot_duration_minutes: int = Field(
        default=20, ge=5, le=120, description="Appointment slot length in minutes"
    )
    max_appointments: int | None = Field(
        default=None,
        ge=1,
        description="Max appointments per day for this block. None = unlimited within window",
    )
    valid_from: date | None = Field(
        default=None, description="Date from which this schedule takes effect"
    )
    valid_until: date | None = Field(
        default=None, description="Last date this schedule is valid"
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "DoctorScheduleCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must be on or after valid_from")
        return self


class DoctorScheduleUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_minutes: int | None = Field(default=None, ge=5, le=120)
    max_appointments: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "DoctorScheduleUpdate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class DoctorScheduleResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    doctor_id: uuid.UUID
    day_of_week: int
    day_name: str
    start_time: time
    end_time: time
    slot_duration_minutes: int
    max_appointments: int | None
    is_active: bool
    valid_from: date | None
    valid_until: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: object) -> "DoctorScheduleResponse":
        d = obj  # type: ignore[assignment]
        return cls(
            id=d.id,
            hospital_id=d.hospital_id,
            doctor_id=d.doctor_id,
            day_of_week=d.day_of_week,
            day_name=_DAY_NAMES[d.day_of_week],
            start_time=d.start_time,
            end_time=d.end_time,
            slot_duration_minutes=d.slot_duration_minutes,
            max_appointments=d.max_appointments,
            is_active=d.is_active,
            valid_from=d.valid_from,
            valid_until=d.valid_until,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )


# ── ScheduleException schemas ──────────────────────────────────────────────────

class ScheduleExceptionCreate(BaseModel):
    exception_type: ScheduleExceptionType
    start_datetime: datetime = Field(description="UTC datetime — start of exception window")
    end_datetime: datetime = Field(description="UTC datetime — end of exception window")
    reason: str | None = Field(default=None, max_length=500)
    is_all_day: bool = Field(default=False, description="True if this blocks the entire day")

    @model_validator(mode="after")
    def validate_range(self) -> "ScheduleExceptionCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class ScheduleExceptionResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    doctor_id: uuid.UUID
    exception_type: ScheduleExceptionType
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None
    is_all_day: bool
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Availability schemas ───────────────────────────────────────────────────────

class AvailableSlot(BaseModel):
    """
    A single available appointment slot.
    All datetimes are UTC ISO 8601. The frontend converts to display timezone.
    This is the response the AI tool layer reads to present options to the patient.
    """

    scheduled_at: datetime = Field(description="Slot start time (UTC)")
    ends_at: datetime = Field(description="Slot end time (UTC)")
    duration_minutes: int
    doctor_id: uuid.UUID
    hospital_id: uuid.UUID
    slot_key: str = Field(
        description="Opaque booking key = ISO datetime string. Pass back in appointment creation."
    )


class DoctorAvailabilityResponse(BaseModel):
    """
    Complete availability response for a doctor over a date range.
    Total_slots is the count of bookable slots remaining.
    """

    doctor_id: uuid.UUID
    hospital_id: uuid.UUID
    date_from: date
    date_to: date
    timezone: str = Field(description="Hospital timezone used for slot generation")
    total_slots: int
    slots: list[AvailableSlot]
