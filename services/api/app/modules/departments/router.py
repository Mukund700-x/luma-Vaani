"""
Departments API router — /api/v1/hospitals/{hospital_id}/departments
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.pagination import Page, PaginationDep
from app.modules.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentSummary,
    DepartmentUpdate,
)
from app.modules.departments.service import DepartmentService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/departments",
    tags=["Departments"],
)


@router.get(
    "/",
    response_model=Page[DepartmentSummary],
    summary="List departments",
    description="List all departments for a hospital. Any authenticated hospital member.",
)
async def list_departments(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    search: str | None = Query(default=None, description="Search by name, slug, or description"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
) -> Page[DepartmentSummary]:
    return await DepartmentService(db).list_departments(
        hospital_id, params=params, search=search, is_active=is_active
    )


@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=201,
    summary="Create department",
    description="**HOSPITAL_ADMIN or SUPER_ADMIN** only. Slug must be unique per hospital.",
)
async def create_department(
    hospital_id: HospitalPathDep,
    payload: DepartmentCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DepartmentResponse:
    return await DepartmentService(db).create_department(hospital_id, payload, actor=current_user)


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Get department",
)
async def get_department(
    hospital_id: HospitalPathDep,
    department_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DepartmentResponse:
    return await DepartmentService(db).get_department(department_id, hospital_id)


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department",
    description="**HOSPITAL_ADMIN or SUPER_ADMIN** only. Partial update — omit fields to keep them unchanged.",
)
async def update_department(
    hospital_id: HospitalPathDep,
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DepartmentResponse:
    return await DepartmentService(db).update_department(
        department_id, hospital_id, payload, actor=current_user
    )


@router.delete(
    "/{department_id}",
    status_code=204,
    summary="Deactivate department",
    description="**HOSPITAL_ADMIN or SUPER_ADMIN** only. Soft-delete — sets `is_active=false`. Cannot be hard-deleted.",
)
async def deactivate_department(
    hospital_id: HospitalPathDep,
    department_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await DepartmentService(db).deactivate_department(
        department_id, hospital_id, actor=current_user
    )
