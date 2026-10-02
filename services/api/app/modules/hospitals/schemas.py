"""
Hospital Pydantic schemas — request/response contracts for the hospitals API.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Config sub-schema ──────────────────────────────────────────────────────────

class HospitalConfig(BaseModel):
    """
    Tenant-level configuration stored as JSONB in the hospitals table.
    All fields have safe defaults so hospitals can be created without full config.
    """

    timezone: str = Field(default="Asia/Kolkata", description="IANA timezone string")
    default_language: str = Field(default="en", description="BCP-47 language code")
    emergency_contact: str | None = Field(
        default=None, description="Emergency phone number shown to patients"
    )
    working_hours_start: str = Field(
        default="09:00", pattern=r"^\d{2}:\d{2}$", description="HH:MM format"
    )
    working_hours_end: str = Field(
        default="18:00", pattern=r"^\d{2}:\d{2}$", description="HH:MM format"
    )
    appointment_slot_duration_minutes: int = Field(
        default=20, ge=5, le=120, description="Default appointment slot length"
    )
    max_advance_booking_days: int = Field(
        default=30, ge=1, le=365, description="How far in advance patients can book"
    )
    cancellation_cutoff_hours: int = Field(
        default=2, ge=0, description="Hours before appointment when cancellation is no longer allowed"
    )


# ── Request schemas ────────────────────────────────────────────────────────────

class HospitalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255, description="Full hospital name")
    slug: str = Field(
        min_length=2,
        max_length=100,
        description="URL-safe identifier (lowercase, hyphens only)",
    )
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=1000)
    config: HospitalConfig = Field(default_factory=HospitalConfig)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens, "
                "starting and ending with alphanumeric character"
            )
        return v


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=1000)
    config: HospitalConfig | None = None
    is_active: bool | None = None


# ── Response schemas ───────────────────────────────────────────────────────────

class HospitalSummary(BaseModel):
    """Lightweight response used in list endpoints."""

    id: uuid.UUID
    name: str
    slug: str
    contact_email: str | None
    contact_phone: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HospitalResponse(BaseModel):
    """Full hospital detail response."""

    id: uuid.UUID
    name: str
    slug: str
    contact_email: str | None
    contact_phone: str | None
    address: str | None
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
