"""
Patients API router — /api/v1/hospitals/{hospital_id}/patients
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.pagination import Page, PaginationDep
from app.modules.patients.schemas import (
    PatientCreate,
    PatientResponse,
    PatientSummary,
    PatientUpdate,
)
from app.modules.patients.service import PatientService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/patients",
    tags=["Patients"],
)


@router.get(
    "/",
    response_model=Page[PatientSummary],
    summary="List patients",
    description=(
        "Paginated patient list for a hospital. "
        "**RECEPTIONIST, DOCTOR, HOSPITAL_ADMIN, SUPER_ADMIN** only. "
        "Search by name, phone, email, or MRN."
    ),
)
async def list_patients(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    search: str | None = Query(default=None, description="Search by name, phone, email, or MRN"),
    is_active: bool | None = Query(default=None),
) -> Page[PatientSummary]:
    return await PatientService(db).list_patients(
        hospital_id, current_user, params=params, search=search, is_active=is_active
    )


@router.post(
    "/",
    response_model=PatientResponse,
    status_code=201,
    summary="Register patient",
    description=(
        "Register a new patient. **RECEPTIONIST or above** only. "
        "MRN must be unique per hospital if provided."
    ),
)
async def create_patient(
    hospital_id: HospitalPathDep,
    payload: PatientCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PatientResponse:
    return await PatientService(db).create_patient(hospital_id, payload, actor=current_user)


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient",
    description="Full patient profile. **RECEPTIONIST or above** only.",
)
async def get_patient(
    hospital_id: HospitalPathDep,
    patient_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PatientResponse:
    return await PatientService(db).get_patient(patient_id, hospital_id, actor=current_user)


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient",
    description=(
        "Partial update of patient record. **RECEPTIONIST or above** only. "
        "Setting `is_active=false` requires **HOSPITAL_ADMIN** or **SUPER_ADMIN**."
    ),
)
async def update_patient(
    hospital_id: HospitalPathDep,
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PatientResponse:
    return await PatientService(db).update_patient(
        patient_id, hospital_id, payload, actor=current_user
    )
