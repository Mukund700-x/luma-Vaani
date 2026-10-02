"""
Doctors API router — /api/v1/hospitals/{hospital_id}/doctors
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.enums import DoctorStatus
from app.core.pagination import Page, PaginationDep
from app.modules.doctors.schemas import (
    DoctorCreate,
    DoctorResponse,
    DoctorSummary,
    DoctorUpdate,
)
from app.modules.doctors.service import DoctorService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/doctors",
    tags=["Doctors"],
)


@router.get(
    "/",
    response_model=Page[DoctorSummary],
    summary="List doctors",
    description=(
        "Paginated list of doctors in a hospital. "
        "Filter by department, status, or search by name/specialization."
    ),
)
async def list_doctors(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    search: str | None = Query(default=None, description="Search by name or specialization"),
    department_id: uuid.UUID | None = Query(default=None, description="Filter by department"),
    status: DoctorStatus | None = Query(default=None, description="Filter by doctor status"),
    is_active: bool | None = Query(default=None),
) -> Page[DoctorSummary]:
    return await DoctorService(db).list_doctors(
        hospital_id,
        params=params,
        search=search,
        department_id=department_id,
        status=status,
        is_active=is_active,
    )


@router.post(
    "/",
    response_model=DoctorResponse,
    status_code=201,
    summary="Create doctor",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Optionally link to an existing user account with `user_id` "
        "and assign to one or more departments."
    ),
)
async def create_doctor(
    hospital_id: HospitalPathDep,
    payload: DoctorCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorResponse:
    return await DoctorService(db).create_doctor(hospital_id, payload, actor=current_user)


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Get doctor",
    description="Full doctor profile including department assignments and consultation fee.",
)
async def get_doctor(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorResponse:
    return await DoctorService(db).get_doctor(doctor_id, hospital_id)


@router.patch(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Update doctor",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. Partial update. "
        "Providing `departments` replaces **all** department assignments."
    ),
)
async def update_doctor(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    payload: DoctorUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorResponse:
    return await DoctorService(db).update_doctor(
        doctor_id, hospital_id, payload, actor=current_user
    )


@router.delete(
    "/{doctor_id}",
    status_code=204,
    summary="Deactivate doctor",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN** only. "
        "Soft-delete — sets `is_active=false` and `status=INACTIVE`. "
        "Existing appointments are not affected; schedule engine will reject new bookings."
    ),
)
async def deactivate_doctor(
    hospital_id: HospitalPathDep,
    doctor_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await DoctorService(db).deactivate_doctor(doctor_id, hospital_id, actor=current_user)
