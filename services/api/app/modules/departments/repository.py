"""
Department repository — tenant-scoped data access.
Every query enforces hospital_id isolation.
"""

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.models import Department


class DepartmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self, department_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Department | None:
        """Fetch by ID, enforcing tenant isolation."""
        result = await self._db.execute(
            select(Department).where(
                and_(
                    Department.id == department_id,
                    Department.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(
        self, slug: str, hospital_id: uuid.UUID
    ) -> Department | None:
        result = await self._db.execute(
            select(Department).where(
                and_(Department.slug == slug, Department.hospital_id == hospital_id)
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Department], int]:
        base_q = select(Department).where(Department.hospital_id == hospital_id)

        if search:
            term = f"%{search}%"
            base_q = base_q.where(
                or_(
                    Department.name.ilike(term),
                    Department.slug.ilike(term),
                    Department.description.ilike(term),
                )
            )
        if is_active is not None:
            base_q = base_q.where(Department.is_active == is_active)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()

        items_q = base_q.order_by(Department.name.asc()).limit(limit).offset(offset)
        items = list((await self._db.execute(items_q)).scalars().all())

        return items, total

    async def create(
        self,
        hospital_id: uuid.UUID,
        **fields: Any,
    ) -> Department:
        dept = Department(hospital_id=hospital_id, **fields)
        self._db.add(dept)
        await self._db.flush()
        await self._db.refresh(dept)
        return dept

    async def update(
        self,
        department_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Department | None:
        await self._db.execute(
            update(Department)
            .where(
                and_(
                    Department.id == department_id,
                    Department.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(department_id, hospital_id)

    async def slug_exists(
        self,
        slug: str,
        hospital_id: uuid.UUID,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        q = select(func.count()).where(
            and_(Department.slug == slug, Department.hospital_id == hospital_id)
        )
        if exclude_id:
            q = q.where(Department.id != exclude_id)
        result = await self._db.execute(q)
        return (result.scalar_one() or 0) > 0
