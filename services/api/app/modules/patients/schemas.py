"""
Patient Pydantic schemas.

PHI fields (name, phone, email, DoB) are present in these schemas for
API transport. They are never written to audit logs — only patient_id is logged.
"""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import BloodGroup, Gender


# ── Sub-schemas ───────────────────────────────────────────────────────────────

class EmergencyContact(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    relationship: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class PatientAddress(BaseModel):
    line1: str | None = Field(default=None, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)


# ── Request schemas ────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    blood_group: BloodGroup | None = None
    preferred_language: str = Field(default="en", max_length=10)
    emergency_contact: EmergencyContact = Field(default_factory=EmergencyContact)
    address: PatientAddress | None = None
    mrn: str | None = Field(
        default=None,
        max_length=100,
        description="Medical Record Number — if not provided, may be auto-assigned by hospital",
    )


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    blood_group: BloodGroup | None = None
    preferred_language: str | None = Field(default=None, max_length=10)
    emergency_contact: EmergencyContact | None = None
    address: PatientAddress | None = None
    is_active: bool | None = None


# ── Response schemas ───────────────────────────────────────────────────────────

class PatientSummary(BaseModel):
    """Lightweight response for list endpoints — omits most PHI."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    mrn: str | None
    full_name: str
    phone: str | None
    gender: Gender | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientResponse(BaseModel):
    """Full patient response — includes all PHI fields."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    mrn: str | None
    full_name: str
    phone: str | None
    email: str | None
    date_of_birth: date | None
    gender: Gender | None
    blood_group: BloodGroup | None
    preferred_language: str
    emergency_contact: dict[str, Any]
    address: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
