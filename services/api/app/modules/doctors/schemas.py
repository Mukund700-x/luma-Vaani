"""
Doctor Pydantic schemas — request/response contracts.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import DoctorStatus
from app.modules.departments.schemas import DepartmentSummary


# ── Department assignment sub-schema ──────────────────────────────────────────

class DoctorDepartmentAssignment(BaseModel):
    """Used in create/update to assign departments to a doctor."""
    department_id: uuid.UUID
    is_primary: bool = False


# ── Request schemas ────────────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    registration_number: str | None = Field(
        default=None,
        max_length=100,
        description="Medical Council of India / NMC registration number",
    )
    specialization: str | None = Field(default=None, max_length=255)
    qualifications: str | None = Field(
        default=None,
        max_length=2000,
        description="e.g. MBBS, MD (Internal Medicine), DM (Cardiology)",
    )
    consultation_fee_inr: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="Consultation fee in INR (stored as paise internally)",
    )
    bio: str | None = Field(default=None, max_length=5000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    user_id: uuid.UUID | None = Field(
        default=None,
        description="Link to an existing User account for doctor login",
    )
    departments: list[DoctorDepartmentAssignment] = Field(
        default_factory=list,
        description="Department assignments. At most one may be primary.",
    )

    @model_validator(mode="after")
    def validate_single_primary(self) -> "DoctorCreate":
        primaries = [d for d in self.departments if d.is_primary]
        if len(primaries) > 1:
            raise ValueError("At most one department can be marked as primary")
        return self


class DoctorUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=255)
    qualifications: str | None = Field(default=None, max_length=2000)
    consultation_fee_inr: Decimal | None = Field(default=None, ge=Decimal("0"))
    bio: str | None = Field(default=None, max_length=5000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    status: DoctorStatus | None = None
    is_active: bool | None = None
    departments: list[DoctorDepartmentAssignment] | None = Field(
        default=None,
        description="If provided, replaces all department assignments",
    )

    @model_validator(mode="after")
    def validate_single_primary(self) -> "DoctorUpdate":
        if self.departments is not None:
            primaries = [d for d in self.departments if d.is_primary]
            if len(primaries) > 1:
                raise ValueError("At most one department can be marked as primary")
        return self


# ── Response schemas ───────────────────────────────────────────────────────────

class DoctorDepartmentLink(BaseModel):
    """Embedded in doctor responses to show department assignments."""
    department_id: uuid.UUID
    is_primary: bool

    model_config = {"from_attributes": True}


class DoctorSummary(BaseModel):
    """Lightweight response for list endpoints."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    full_name: str
    specialization: str | None
    status: DoctorStatus
    avatar_url: str | None
    consultation_fee_inr: float | None
    primary_department_id: uuid.UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class DoctorResponse(BaseModel):
    """Full doctor detail response."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    user_id: uuid.UUID | None
    full_name: str
    registration_number: str | None
    specialization: str | None
    qualifications: str | None
    consultation_fee_inr: float | None
    bio: str | None
    avatar_url: str | None
    status: DoctorStatus
    is_active: bool
    departments: list[DoctorDepartmentLink]
    primary_department_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_links(cls, doctor: object) -> "DoctorResponse":
        """Build response from Doctor ORM object (already has department_links loaded)."""
        d = doctor  # type: ignore[assignment]
        return cls(
            id=d.id,
            hospital_id=d.hospital_id,
            user_id=d.user_id,
            full_name=d.full_name,
            registration_number=d.registration_number,
            specialization=d.specialization,
            qualifications=d.qualifications,
            consultation_fee_inr=d.consultation_fee_inr,
            bio=d.bio,
            avatar_url=d.avatar_url,
            status=d.status,
            is_active=d.is_active,
            departments=[
                DoctorDepartmentLink(
                    department_id=link.department_id,
                    is_primary=link.is_primary,
                )
                for link in d.department_links
            ],
            primary_department_id=d.primary_department_id,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
