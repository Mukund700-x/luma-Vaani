"""
Doctor repository — tenant-scoped data access for doctors and their department links.
"""

import uuid
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.doctors.models import Doctor, DoctorDepartment


class DoctorRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self, doctor_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Doctor | None:
        """Fetch doctor with department_links pre-loaded. Enforces hospital_id."""
        result = await self._db.execute(
            select(Doctor)
            .options(selectinload(Doctor.department_links))
            .where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        search: str | None = None,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
        is_active: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Doctor], int]:
        """
        Paginated doctor list with optional filters.
        Joins DoctorDepartment when filtering by department.
        """
        base_q = (
            select(Doctor)
            .options(selectinload(Doctor.department_links))
            .where(Doctor.hospital_id == hospital_id)
        )

        if search:
            term = f"%{search}%"
            base_q = base_q.where(
                or_(
                    Doctor.full_name.ilike(term),
                    Doctor.specialization.ilike(term),
                    Doctor.registration_number.ilike(term),
                )
            )
        if department_id:
            base_q = base_q.join(
                DoctorDepartment,
                and_(
                    DoctorDepartment.doctor_id == Doctor.id,
                    DoctorDepartment.department_id == department_id,
                ),
            )
        if status:
            base_q = base_q.where(Doctor.status == status)
        if is_active is not None:
            base_q = base_q.where(Doctor.is_active == is_active)

        count_q = select(func.count()).select_from(
            base_q.with_only_columns(Doctor.id).subquery()
        )
        total: int = (await self._db.execute(count_q)).scalar_one()

        items_q = base_q.order_by(Doctor.full_name.asc()).limit(limit).offset(offset)
        items = list((await self._db.execute(items_q)).scalars().all())

        return items, total

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> Doctor:
        doctor = Doctor(hospital_id=hospital_id, **fields)
        self._db.add(doctor)
        await self._db.flush()
        await self._db.refresh(doctor, attribute_names=["department_links"])
        return doctor

    async def update(
        self,
        doctor_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Doctor | None:
        await self._db.execute(
            update(Doctor)
            .where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(doctor_id, hospital_id)

    # ── Department link management ─────────────────────────────────────────────

    async def set_department_links(
        self,
        doctor_id: uuid.UUID,
        assignments: list[dict[str, Any]],
    ) -> None:
        """
        Replace all department assignments for a doctor atomically.
        assignments: [{"department_id": UUID, "is_primary": bool}]
        """
        # Remove existing links
        await self._db.execute(
            delete(DoctorDepartment).where(DoctorDepartment.doctor_id == doctor_id)
        )
        # Insert new links
        for assignment in assignments:
            link = DoctorDepartment(
                doctor_id=doctor_id,
                department_id=assignment["department_id"],
                is_primary=assignment.get("is_primary", False),
            )
            self._db.add(link)

        await self._db.flush()

    async def user_id_in_hospital(
        self, user_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> bool:
        """Verify a user_id exists in the given hospital before linking."""
        from app.modules.auth.models import User  # local import to avoid circular

        result = await self._db.execute(
            select(func.count()).where(
                and_(
                    User.id == user_id,
                    User.hospital_id == hospital_id,
                )
            )
        )
        return (result.scalar_one() or 0) > 0
