"""
Patient repository — tenant-scoped, PHI-safe data access.
"""

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.patients.models import Patient


class PatientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self, patient_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Patient | None:
        """Always enforces hospital_id — cross-tenant fetch returns None."""
        result = await self._db.execute(
            select(Patient).where(
                and_(
                    Patient.id == patient_id,
                    Patient.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_mrn(self, mrn: str, hospital_id: uuid.UUID) -> Patient | None:
        result = await self._db.execute(
            select(Patient).where(
                and_(Patient.mrn == mrn, Patient.hospital_id == hospital_id)
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
    ) -> tuple[list[Patient], int]:
        """
        Paginated patient list.
        Search matches on full_name, phone, email, or MRN.
        NOTE: search is case-insensitive ilike — appropriate for staff lookup.
        """
        base_q = select(Patient).where(Patient.hospital_id == hospital_id)

        if search:
            term = f"%{search}%"
            base_q = base_q.where(
                or_(
                    Patient.full_name.ilike(term),
                    Patient.phone.ilike(term),
                    Patient.email.ilike(term),
                    Patient.mrn.ilike(term),
                )
            )
        if is_active is not None:
            base_q = base_q.where(Patient.is_active == is_active)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()

        items_q = (
            base_q.order_by(Patient.full_name.asc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await self._db.execute(items_q)).scalars().all())

        return items, total

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> Patient:
        patient = Patient(hospital_id=hospital_id, **fields)
        self._db.add(patient)
        await self._db.flush()
        await self._db.refresh(patient)
        return patient

    async def update(
        self,
        patient_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Patient | None:
        await self._db.execute(
            update(Patient)
            .where(
                and_(
                    Patient.id == patient_id,
                    Patient.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(patient_id, hospital_id)

    async def mrn_exists(
        self,
        mrn: str,
        hospital_id: uuid.UUID,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        q = select(func.count()).where(
            and_(Patient.mrn == mrn, Patient.hospital_id == hospital_id)
        )
        if exclude_id:
            q = q.where(Patient.id != exclude_id)
        result = await self._db.execute(q)
        return (result.scalar_one() or 0) > 0
