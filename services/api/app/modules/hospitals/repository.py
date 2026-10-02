"""
Hospital repository — tenant-safe data access layer.
All queries include hospital_id where applicable.
"""

import uuid
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hospitals.models import Hospital


class HospitalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, hospital_id: uuid.UUID) -> Hospital | None:
        result = await self._db.execute(
            select(Hospital).where(Hospital.id == hospital_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Hospital | None:
        result = await self._db.execute(
            select(Hospital).where(Hospital.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        is_active: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Hospital], int]:
        """List all hospitals (SUPER_ADMIN only). Returns (items, total)."""
        base_q = select(Hospital)

        if search:
            term = f"%{search}%"
            base_q = base_q.where(
                or_(
                    Hospital.name.ilike(term),
                    Hospital.slug.ilike(term),
                    Hospital.contact_email.ilike(term),
                )
            )
        if is_active is not None:
            base_q = base_q.where(Hospital.is_active == is_active)

        count_q = select(func.count()).select_from(base_q.subquery())
        total_result = await self._db.execute(count_q)
        total: int = total_result.scalar_one()

        items_q = base_q.order_by(Hospital.name.asc()).limit(limit).offset(offset)
        items_result = await self._db.execute(items_q)
        items = list(items_result.scalars().all())

        return items, total

    async def create(
        self,
        *,
        name: str,
        slug: str,
        contact_email: str | None,
        contact_phone: str | None,
        address: str | None,
        config: dict[str, Any],
    ) -> Hospital:
        hospital = Hospital(
            name=name,
            slug=slug,
            contact_email=contact_email,
            contact_phone=contact_phone,
            address=address,
            config=config,
            is_active=True,
        )
        self._db.add(hospital)
        await self._db.flush()
        await self._db.refresh(hospital)
        return hospital

    async def update(
        self,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Hospital | None:
        await self._db.execute(
            update(Hospital)
            .where(Hospital.id == hospital_id)
            .values(**fields)
        )
        return await self.get_by_id(hospital_id)

    async def slug_exists(self, slug: str, exclude_id: uuid.UUID | None = None) -> bool:
        q = select(func.count()).where(Hospital.slug == slug)
        if exclude_id:
            q = q.where(Hospital.id != exclude_id)
        result = await self._db.execute(q)
        return (result.scalar_one() or 0) > 0
