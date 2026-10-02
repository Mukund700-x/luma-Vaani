"""
Appointment Pydantic schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import AppointmentSource, AppointmentStatus, AppointmentType


# ── Request schemas ────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID
    scheduled_at: datetime = Field(
        description=(
            "UTC datetime for the appointment. "
            "Must match a slot_key from the /availability endpoint. "
            "The backend validates this against live availability."
        )
    )
    appointment_type: AppointmentType = Field(default=AppointmentType.OPD)
    source: AppointmentSource = Field(default=AppointmentSource.WEB)
    notes: str | None = Field(default=None, max_length=2000)
    chief_complaint: str | None = Field(
        default=None,
        max_length=1000,
        description="Patient-reported reason for visit (PHI — not logged)",
    )
    # AI conversation that triggered this booking (Phase 4)
    conversation_id: uuid.UUID | None = None


class AppointmentCancelRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Reason for cancellation",
    )


class AppointmentRescheduleRequest(BaseModel):
    new_scheduled_at: datetime = Field(
        description="UTC datetime for the new slot (must be available)"
    )
    reason: str | None = Field(default=None, max_length=500)


class AppointmentStatusUpdate(BaseModel):
    """Admin-only status transitions: CONFIRMED → COMPLETED, NO_SHOW."""
    status: AppointmentStatus


# ── Response schemas ───────────────────────────────────────────────────────────

class AppointmentSummary(BaseModel):
    """Lightweight response for list endpoints."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID
    scheduled_at: datetime
    ends_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    appointment_type: AppointmentType
    source: AppointmentSource
    token_number: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentResponse(BaseModel):
    """Full appointment detail."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    department_id: uuid.UUID
    scheduled_at: datetime
    ends_at: datetime
    duration_minutes: int
    status: AppointmentStatus
    appointment_type: AppointmentType
    source: AppointmentSource
    conversation_id: uuid.UUID | None
    notes: str | None
    chief_complaint: str | None
    cancellation_reason: str | None
    cancelled_at: datetime | None
    cancelled_by_user_id: uuid.UUID | None
    rescheduled_from_id: uuid.UUID | None
    token_number: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
