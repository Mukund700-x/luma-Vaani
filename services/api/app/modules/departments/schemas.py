"""
Department Pydantic schemas.
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Request schemas ────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Department full name")
    slug: str = Field(
        min_length=1, max_length=100, description="URL-safe slug (unique per hospital)"
    )
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(
        default=None,
        description="Hex color for UI e.g. #4A90E2",
        max_length=7,
    )
    icon: str | None = Field(
        default=None,
        description="Icon key for frontend e.g. 'heart', 'brain', 'bone'",
        max_length=50,
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens only"
            )
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code e.g. #4A90E2")
        return v


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code e.g. #4A90E2")
        return v


# ── Response schemas ───────────────────────────────────────────────────────────

class DepartmentSummary(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    slug: str
    color: str | None
    icon: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    color: str | None
    icon: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
