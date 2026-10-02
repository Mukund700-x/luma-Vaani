"""
Hospitals API router — /api/v1/hospitals
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep, require_roles
from app.core.enums import UserRole
from app.core.pagination import Page, PaginationDep
from app.modules.hospitals.schemas import (
    HospitalCreate,
    HospitalResponse,
    HospitalSummary,
    HospitalUpdate,
)
from app.modules.hospitals.service import HospitalService

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.get(
    "/",
    response_model=Page[HospitalSummary],
    summary="List hospitals",
    description=(
        "**SUPER_ADMIN**: paginated list of all hospitals with search and filter. "
        "**HOSPITAL_ADMIN / staff**: returns only their own hospital."
    ),
)
async def list_hospitals(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    search: str | None = Query(default=None, description="Search by name, slug, or email"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
) -> Page[HospitalSummary]:
    return await HospitalService(db).list_hospitals(
        actor=current_user, params=params, search=search, is_active=is_active
    )


@router.post(
    "/",
    response_model=HospitalResponse,
    status_code=201,
    summary="Create hospital",
    description="**SUPER_ADMIN only.** Creates a new tenant hospital.",
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)
async def create_hospital(
    payload: HospitalCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HospitalResponse:
    return await HospitalService(db).create_hospital(payload, actor=current_user)


@router.get(
    "/{hospital_id}",
    response_model=HospitalResponse,
    summary="Get hospital",
    description="Fetch a hospital by ID. Tenant-scoped — users can only see their own hospital.",
)
async def get_hospital(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HospitalResponse:
    return await HospitalService(db).get_hospital(hospital_id, actor=current_user)


@router.patch(
    "/{hospital_id}",
    response_model=HospitalResponse,
    summary="Update hospital",
    description=(
        "**SUPER_ADMIN**: can update all fields including `is_active`. "
        "**HOSPITAL_ADMIN**: can update name, contact details, and config."
    ),
)
async def update_hospital(
    hospital_id: HospitalPathDep,
    payload: HospitalUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HospitalResponse:
    return await HospitalService(db).update_hospital(hospital_id, payload, actor=current_user)
