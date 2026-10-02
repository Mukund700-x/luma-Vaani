"""
Appointments API router — /api/v1/hospitals/{hospital_id}/appointments
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.enums import AppointmentStatus
from app.core.pagination import Page, PaginationDep
from app.modules.appointments.schemas import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AppointmentSummary,
    AppointmentStatusUpdate,
)
from app.modules.appointments.service import AppointmentService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/appointments",
    tags=["Appointments"],
)


@router.get(
    "/",
    response_model=Page[AppointmentSummary],
    summary="List appointments",
    description=(
        "Paginated appointment list for a hospital. "
        "Filter by patient, doctor, department, status, or date range. "
        "Default order: chronological ascending."
    ),
)
async def list_appointments(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    patient_id: uuid.UUID | None = Query(default=None),
    doctor_id: uuid.UUID | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    date_from: datetime | None = Query(default=None, description="UTC datetime lower bound"),
    date_to: datetime | None = Query(default=None, description="UTC datetime upper bound"),
) -> Page[AppointmentSummary]:
    return await AppointmentService(db).list_appointments(
        hospital_id,
        current_user,
        params=params,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.post(
    "/",
    response_model=AppointmentResponse,
    status_code=201,
    summary="Book appointment",
    description=(
        "**Book an appointment for a patient.** "
        "The `scheduled_at` datetime must match a `slot_key` from the "
        "`GET /hospitals/{hospital_id}/doctors/{doctor_id}/availability` endpoint. "
        "The backend validates availability, enforces the DB double-booking guard, "
        "and returns the confirmed appointment. "
        "If the slot is taken between availability check and booking, a 409 is returned."
    ),
)
async def create_appointment(
    hospital_id: HospitalPathDep,
    payload: AppointmentCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentResponse:
    return await AppointmentService(db).create_appointment(
        hospital_id, payload, actor=current_user
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment",
)
async def get_appointment(
    hospital_id: HospitalPathDep,
    appointment_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentResponse:
    return await AppointmentService(db).get_appointment(
        appointment_id, hospital_id, actor=current_user
    )


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel appointment",
    description=(
        "Cancel a PENDING or CONFIRMED appointment. "
        "Hospital config `cancellation_cutoff_hours` enforces a minimum notice period "
        "for non-admin users. Admins and receptionists can cancel at any time."
    ),
)
async def cancel_appointment(
    hospital_id: HospitalPathDep,
    appointment_id: uuid.UUID,
    payload: AppointmentCancelRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentResponse:
    return await AppointmentService(db).cancel_appointment(
        appointment_id, hospital_id, payload, actor=current_user
    )


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    status_code=201,
    summary="Reschedule appointment",
    description=(
        "Move an appointment to a new time slot. "
        "Marks the original as RESCHEDULED and creates a new CONFIRMED appointment. "
        "If the new slot is unavailable, the original appointment is preserved unchanged. "
        "Returns the **new** appointment."
    ),
)
async def reschedule_appointment(
    hospital_id: HospitalPathDep,
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentResponse:
    return await AppointmentService(db).reschedule_appointment(
        appointment_id, hospital_id, payload, actor=current_user
    )


@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentResponse,
    summary="Update appointment status",
    description=(
        "**RECEPTIONIST, DOCTOR, HOSPITAL_ADMIN, SUPER_ADMIN** only. "
        "Allowed transitions: CONFIRMED → COMPLETED | NO_SHOW. "
        "Use the dedicated `/cancel` and `/reschedule` endpoints for those workflows."
    ),
)
async def update_status(
    hospital_id: HospitalPathDep,
    appointment_id: uuid.UUID,
    payload: AppointmentStatusUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentResponse:
    return await AppointmentService(db).update_status(
        appointment_id, hospital_id, payload.status, actor=current_user
    )
