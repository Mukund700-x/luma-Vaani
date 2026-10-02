"""
Schedules API router — /api/v1/hospitals/{hospital_id}/doctors/{doctor_id}/...

Covers:
  GET/POST/GET/PATCH/DELETE  /schedules
  GET/POST/DELETE            /exceptions
  GET                        /availability   ← the key endpoint for AI tools
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import date

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.modules.schedules.schemas import (
    DoctorAvailabilityResponse,
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    DoctorScheduleUpdate,
    ScheduleExceptionCreate,
    ScheduleExceptionResponse,
)
from app.modules.schedules.service import ScheduleService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/doctors/{doctor_id}",
    tags=["Schedules & Availability"],
)


# ── Doctor Schedules ───────────────────────────────────────────────────────────

@router.get(
    "/schedules",
    response_model=list[DoctorScheduleResponse],
    summary="List doctor schedules",
    description="All recurring weekly schedule blocks for a doctor. Any authenticated hospital member.",
)
async def list_schedules(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False, description="Include deactivated schedules"),
) -> list[DoctorScheduleResponse]:
    return await ScheduleService(db).list_schedules(
        doctor_id, hospital_id, include_inactive=include_inactive
    )


@router.post(
    "/schedules",
    response_model=DoctorScheduleResponse,
    status_code=201,
    summary="Create schedule block",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Creates a recurring weekly availability window. "
        "Multiple blocks can exist for the same day (e.g., morning + afternoon sessions)."
    ),
)
async def create_schedule(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    payload: DoctorScheduleCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorScheduleResponse:
    return await ScheduleService(db).create_schedule(
        doctor_id, hospital_id, payload, actor=current_user
    )


@router.patch(
    "/schedules/{schedule_id}",
    response_model=DoctorScheduleResponse,
    summary="Update schedule block",
    description="**HOSPITAL_ADMIN or SUPER_ADMIN** only. Partial update.",
)
async def update_schedule(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    schedule_id: uuid.UUID,
    payload: DoctorScheduleUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorScheduleResponse:
    return await ScheduleService(db).update_schedule(
        schedule_id, hospital_id, payload, actor=current_user
    )


@router.delete(
    "/schedules/{schedule_id}",
    status_code=204,
    summary="Deactivate schedule block",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Soft-delete — sets `is_active=false`. "
        "Existing appointments are not affected."
    ),
)
async def delete_schedule(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    schedule_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await ScheduleService(db).delete_schedule(
        schedule_id, hospital_id, actor=current_user
    )


# ── Schedule Exceptions ────────────────────────────────────────────────────────

@router.get(
    "/exceptions",
    response_model=list[ScheduleExceptionResponse],
    summary="List schedule exceptions",
    description="Leaves, holidays, and blocked periods for a doctor. Any authenticated member.",
)
async def list_exceptions(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    from_dt: datetime | None = Query(default=None, description="Filter exceptions from this UTC datetime"),
    to_dt: datetime | None = Query(default=None, description="Filter exceptions until this UTC datetime"),
) -> list[ScheduleExceptionResponse]:
    return await ScheduleService(db).list_exceptions(
        doctor_id, hospital_id, from_dt=from_dt, to_dt=to_dt
    )


@router.post(
    "/exceptions",
    response_model=ScheduleExceptionResponse,
    status_code=201,
    summary="Create schedule exception",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Block a doctor's availability for a specific period "
        "(LEAVE, HOLIDAY, BLOCKED). The AvailabilityEngine automatically "
        "excludes slots overlapping with active exceptions."
    ),
)
async def create_exception(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    payload: ScheduleExceptionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduleExceptionResponse:
    return await ScheduleService(db).create_exception(
        doctor_id, hospital_id, payload, actor=current_user
    )


@router.delete(
    "/exceptions/{exception_id}",
    status_code=204,
    summary="Delete schedule exception",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Hard-delete (exceptions are immutable — remove and recreate if changes needed)."
    ),
)
async def delete_exception(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    exception_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await ScheduleService(db).delete_exception(
        exception_id, hospital_id, actor=current_user
    )


# ── Availability ───────────────────────────────────────────────────────────────

@router.get(
    "/availability",
    response_model=DoctorAvailabilityResponse,
    summary="Get doctor availability",
    description=(
        "**Returns all bookable appointment slots for a doctor over a date range.** "
        "This is the primary endpoint consumed by the AI tool layer. "
        "Slots are pre-filtered for exceptions, existing bookings, and past times. "
        "The `slot_key` field in each slot is passed back verbatim when creating an appointment. "
        "Date range limited to 90 days. "
        "All datetimes returned as UTC ISO 8601."
    ),
)
async def get_availability(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(description="Start date (inclusive), format: YYYY-MM-DD"),
    date_to: date = Query(description="End date (inclusive), format: YYYY-MM-DD"),
    department_id: uuid.UUID | None = Query(
        default=None, description="Filter slots for a specific department"
    ),
) -> DoctorAvailabilityResponse:
    return await ScheduleService(db).get_availability(
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        date_from=date_from,
        date_to=date_to,
        primary_department_id=department_id,
    )
