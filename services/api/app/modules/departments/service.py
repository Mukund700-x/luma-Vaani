"""
Department service — business logic, tenant enforcement, and audit logging.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.enums import AuditActorType, UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.departments.models import Department
from app.modules.departments.repository import DepartmentRepository
from app.modules.departments.schemas import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentSummary,
    DepartmentUpdate,
)

logger = structlog.get_logger(__name__)

# Roles that may create / update / deactivate departments
_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}


class DepartmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = DepartmentRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_or_404(
        self, department_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Department:
        dept = await self._repo.get_by_id(department_id, hospital_id)
        if not dept:
            raise NotFoundException("Department", str(department_id))
        return dept

    def _assert_admin(self, actor: User) -> None:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Only HOSPITAL_ADMIN or SUPER_ADMIN can manage departments")

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_departments(
        self,
        hospital_id: uuid.UUID,
        *,
        params: PageParams,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> Page[DepartmentSummary]:
        items, total = await self._repo.list(
            hospital_id,
            search=search,
            is_active=is_active,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [DepartmentSummary.model_validate(d) for d in items],
            total,
            params,
        )

    async def get_department(
        self, department_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> DepartmentResponse:
        dept = await self._get_or_404(department_id, hospital_id)
        return DepartmentResponse.model_validate(dept)

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create_department(
        self,
        hospital_id: uuid.UUID,
        payload: DepartmentCreate,
        actor: User,
    ) -> DepartmentResponse:
        self._assert_admin(actor)

        if await self._repo.slug_exists(payload.slug, hospital_id):
            raise ConflictException(
                f"Department slug '{payload.slug}' already exists in this hospital"
            )

        dept = await self._repo.create(
            hospital_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
        )

        await self._audit.log(
            action="department.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="department",
            resource_id=str(dept.id),
            after_state={"name": dept.name, "slug": dept.slug},
        )
        logger.info("department_created", dept_id=str(dept.id), hospital_id=str(hospital_id))
        return DepartmentResponse.model_validate(dept)

    async def update_department(
        self,
        department_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: DepartmentUpdate,
        actor: User,
    ) -> DepartmentResponse:
        self._assert_admin(actor)
        dept = await self._get_or_404(department_id, hospital_id)

        before = {"name": dept.name, "is_active": dept.is_active}

        fields: dict = {}
        if payload.name is not None:
            fields["name"] = payload.name
        if payload.description is not None:
            fields["description"] = payload.description
        if payload.color is not None:
            fields["color"] = payload.color
        if payload.icon is not None:
            fields["icon"] = payload.icon
        if payload.is_active is not None:
            fields["is_active"] = payload.is_active

        if not fields:
            return DepartmentResponse.model_validate(dept)

        updated = await self._repo.update(department_id, hospital_id, fields)

        await self._audit.log(
            action="department.update",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="department",
            resource_id=str(department_id),
            before_state=before,
            after_state=fields,
        )
        logger.info("department_updated", dept_id=str(department_id))
        return DepartmentResponse.model_validate(updated)

    async def deactivate_department(
        self,
        department_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        """Soft-delete: sets is_active=False. Hard deletes are not permitted."""
        self._assert_admin(actor)
        dept = await self._get_or_404(department_id, hospital_id)

        await self._repo.update(department_id, hospital_id, {"is_active": False})

        await self._audit.log(
            action="department.deactivate",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="department",
            resource_id=str(department_id),
            before_state={"name": dept.name, "is_active": True},
        )
        logger.info("department_deactivated", dept_id=str(department_id))
