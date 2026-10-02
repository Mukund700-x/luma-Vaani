"""
AvailabilityEngine — the single source of truth for doctor appointment availability.

ARCHITECTURE RULE (from ADR-003):
    The AI MUST NEVER compute availability. All availability queries MUST go through
    this engine. The engine reads fresh data from the DB on every call.

Algorithm (per doctor, per date range):
    1. Load active DoctorSchedules valid for the date range
    2. Load ScheduleExceptions (LEAVE / HOLIDAY / BLOCKED) overlapping the range
    3. Load existing confirmed/pending appointments in the range
    4. For each calendar day in [date_from, date_to]:
        a. Find schedules for that day-of-week
        b. For each schedule: generate theoretical slot grid
        c. Remove slots blocked by exceptions (overlap check)
        d. Remove slots already occupied by appointments
        e. Apply max_appointments cap if configured
    5. Return sorted list of AvailableSlot objects

Timezone handling:
    - DoctorSchedule.start_time / end_time are wall-clock local times (no tz)
    - All slot datetimes are generated in the hospital's local timezone and
      stored/returned as UTC (TIMESTAMPTZ)
    - ZoneInfo is used (Python 3.9+, tzdata package required)
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from app.modules.schedules.models import DoctorSchedule, ScheduleException
from app.modules.schedules.repository import ScheduleRepository

if TYPE_CHECKING:
    from app.modules.appointments.repository import AppointmentRepository

logger = structlog.get_logger(__name__)

_UTC = ZoneInfo("UTC")
_DEFAULT_TZ = ZoneInfo("Asia/Kolkata")
_DEFAULT_SLOT_DURATION = 20  # minutes


@dataclass(frozen=True, order=True)
class AvailableSlotInternal:
    """
    Internal representation used by the engine.
    Converted to the API schema (AvailableSlot) before leaving the service layer.
    """

    scheduled_at: datetime   # UTC, timezone-aware
    ends_at: datetime        # UTC, timezone-aware
    duration_minutes: int
    doctor_id: uuid.UUID = field(compare=False)
    hospital_id: uuid.UUID = field(compare=False)
    primary_department_id: uuid.UUID | None = field(default=None, compare=False)


class AvailabilityEngine:
    """
    Stateless availability computation engine.
    Instantiated per request; not a singleton.
    """

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        appointment_repo: "AppointmentRepository",
    ) -> None:
        self._schedule_repo = schedule_repo
        self._apt_repo = appointment_repo

    # ── Public API ─────────────────────────────────────────────────────────────

    async def get_available_slots(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        date_from: date,
        date_to: date,
        hospital_timezone: str = "Asia/Kolkata",
        primary_department_id: uuid.UUID | None = None,
    ) -> list[AvailableSlotInternal]:
        """
        Compute all available appointment slots for a doctor over a date range.

        Returns:
            Sorted list of AvailableSlotInternal, each representing a bookable window.
        """
        if date_from > date_to:
            return []

        # Guard: never allow ranges > 90 days (performance + UX)
        if (date_to - date_from).days > 90:
            raise ValueError("Availability query range cannot exceed 90 days")

        tz = self._resolve_timezone(hospital_timezone)

        # ── 1. Load schedules valid for the range ─────────────────────────────
        schedules = await self._schedule_repo.get_active_schedules_for_range(
            doctor_id, hospital_id, date_from, date_to
        )
        if not schedules:
            logger.debug(
                "no_schedules_found",
                doctor_id=str(doctor_id),
                date_from=str(date_from),
                date_to=str(date_to),
            )
            return []

        # ── 2. Compute UTC range boundaries for bulk queries ──────────────────
        range_start_utc = datetime.combine(date_from, time.min, tzinfo=tz).astimezone(_UTC)
        range_end_utc = datetime.combine(date_to, time.max, tzinfo=tz).astimezone(_UTC)

        # ── 3. Load exceptions (LEAVE / HOLIDAY / BLOCKED) in range ──────────
        exceptions = await self._schedule_repo.get_exceptions_in_range(
            doctor_id, range_start_utc, range_end_utc
        )

        # ── 4. Load booked slots in range (set of scheduled_at UTC datetimes) ─
        booked_datetimes: set[datetime] = await self._apt_repo.get_booked_datetimes(
            doctor_id, range_start_utc, range_end_utc
        )

        # ── 5. Generate slots day by day ──────────────────────────────────────
        slots: list[AvailableSlotInternal] = []
        current_date = date_from

        while current_date <= date_to:
            day_of_week = current_date.weekday()  # 0=Mon, 6=Sun

            day_schedules = [
                s for s in schedules
                if s.day_of_week == day_of_week
                and self._schedule_valid_on(s, current_date)
            ]

            for schedule in day_schedules:
                day_slots = self._generate_day_slots(
                    day=current_date,
                    schedule=schedule,
                    tz=tz,
                    doctor_id=doctor_id,
                    hospital_id=hospital_id,
                    primary_department_id=primary_department_id,
                )

                # Filter: remove slots blocked by exceptions
                day_slots = [
                    s for s in day_slots
                    if not self._is_blocked_by_exception(s, exceptions)
                ]

                # Filter: remove already-booked slots
                day_slots = [
                    s for s in day_slots
                    if s.scheduled_at not in booked_datetimes
                ]

                # Filter: remove past slots (safety guard)
                now_utc = datetime.now(_UTC)
                day_slots = [s for s in day_slots if s.scheduled_at > now_utc]

                # Apply max_appointments cap
                if schedule.max_appointments is not None:
                    already_booked_today = self._count_booked_on_date(
                        current_date, booked_datetimes, tz
                    )
                    remaining = max(0, schedule.max_appointments - already_booked_today)
                    day_slots = day_slots[:remaining]

                slots.extend(day_slots)

            current_date += timedelta(days=1)

        slots.sort(key=lambda s: s.scheduled_at)

        logger.info(
            "availability_computed",
            doctor_id=str(doctor_id),
            hospital_id=str(hospital_id),
            date_from=str(date_from),
            date_to=str(date_to),
            total_slots=len(slots),
        )
        return slots

    async def validate_slot(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        scheduled_at: datetime,
        hospital_timezone: str = "Asia/Kolkata",
    ) -> tuple[bool, str, int]:
        """
        Validate a specific requested slot before booking.

        Returns:
            (is_valid: bool, reason_if_invalid: str, slot_duration_minutes: int)

        This is a targeted check used by AppointmentService.create_appointment.
        It is significantly cheaper than computing full availability.
        """
        tz = self._resolve_timezone(hospital_timezone)

        # Ensure UTC-aware
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=_UTC)
        scheduled_at_utc = scheduled_at.astimezone(_UTC)

        # 1. Must be in the future
        if scheduled_at_utc <= datetime.now(_UTC):
            return False, "Cannot book appointments in the past", 0

        # 2. Must fall within an active schedule window (local time)
        local_dt = scheduled_at_utc.astimezone(tz)
        target_date = local_dt.date()
        wall_time = local_dt.time()

        duration = await self._schedule_repo.get_slot_duration_for_datetime(
            doctor_id, hospital_id, target_date, wall_time
        )
        if duration is None:
            return (
                False,
                "No active schedule found for this doctor at the requested time",
                0,
            )

        # 3. Must not be blocked by an exception
        slot_end_utc = scheduled_at_utc + timedelta(minutes=duration)
        exceptions = await self._schedule_repo.get_exceptions_in_range(
            doctor_id, scheduled_at_utc, slot_end_utc
        )
        if exceptions:
            exc_type = exceptions[0].exception_type.value
            return False, f"Doctor is unavailable at this time ({exc_type})", 0

        # 4. Must not already be booked
        already_taken = await self._apt_repo.is_slot_taken(doctor_id, scheduled_at_utc)
        if already_taken:
            return False, "This time slot is already booked", 0

        return True, "", duration

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_timezone(tz_name: str) -> ZoneInfo:
        """Safely resolve an IANA timezone string; falls back to IST."""
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            logger.warning("invalid_timezone", tz_name=tz_name, fallback="Asia/Kolkata")
            return _DEFAULT_TZ

    @staticmethod
    def _schedule_valid_on(schedule: DoctorSchedule, target_date: date) -> bool:
        """Check if a DoctorSchedule is valid on a specific calendar date."""
        if schedule.valid_from and target_date < schedule.valid_from:
            return False
        if schedule.valid_until and target_date > schedule.valid_until:
            return False
        return True

    @staticmethod
    def _generate_day_slots(
        day: date,
        schedule: DoctorSchedule,
        tz: ZoneInfo,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        primary_department_id: uuid.UUID | None,
    ) -> list[AvailableSlotInternal]:
        """
        Generate all theoretical slots for one schedule block on one day.
        Slots are non-overlapping and aligned to slot_duration_minutes.
        """
        duration_td = timedelta(minutes=schedule.slot_duration_minutes)

        # Build timezone-aware local datetimes for start/end
        block_start = datetime(
            day.year, day.month, day.day,
            schedule.start_time.hour, schedule.start_time.minute,
            tzinfo=tz,
        )
        block_end = datetime(
            day.year, day.month, day.day,
            schedule.end_time.hour, schedule.end_time.minute,
            tzinfo=tz,
        )

        slots = []
        cursor = block_start

        while cursor + duration_td <= block_end:
            slot_end = cursor + duration_td
            slots.append(
                AvailableSlotInternal(
                    scheduled_at=cursor.astimezone(_UTC),
                    ends_at=slot_end.astimezone(_UTC),
                    duration_minutes=schedule.slot_duration_minutes,
                    doctor_id=doctor_id,
                    hospital_id=hospital_id,
                    primary_department_id=primary_department_id,
                )
            )
            cursor = slot_end  # strict non-overlap: next slot starts exactly where this ends

        return slots

    @staticmethod
    def _is_blocked_by_exception(
        slot: AvailableSlotInternal,
        exceptions: list[ScheduleException],
    ) -> bool:
        """
        Returns True if the slot overlaps with any blocking exception.
        Overlap condition: slot_start < exc_end AND slot_end > exc_start
        """
        for exc in exceptions:
            if slot.scheduled_at < exc.end_datetime and slot.ends_at > exc.start_datetime:
                return True
        return False

    @staticmethod
    def _count_booked_on_date(
        target_date: date,
        booked_datetimes: set[datetime],
        tz: ZoneInfo,
    ) -> int:
        """Count existing bookings on a specific calendar date (in hospital timezone)."""
        count = 0
        for dt in booked_datetimes:
            local_dt = dt.astimezone(tz)
            if local_dt.date() == target_date:
                count += 1
        return count
