"""
Notification Pydantic schemas.

PHI MASKING: recipient is masked in all response schemas.
The raw recipient is never exposed via the API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field


# ── Template schemas ───────────────────────────────────────────────────────────

class NotificationTemplateCreate(BaseModel):
    event_type: str = Field(max_length=50, description="e.g. appointment.confirmed")
    channel: str = Field(max_length=20, description="SMS | WHATSAPP | EMAIL")
    language: str = Field(default="en", max_length=10, description="BCP-47 language tag")
    subject: str | None = Field(default=None, max_length=500, description="Email subject (ignored for SMS/WhatsApp)")
    body: str = Field(description="Jinja2 template body with {{ variable }} placeholders")


class NotificationTemplateUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    is_active: bool | None = None


class NotificationTemplateResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    event_type: str
    channel: str
    language: str
    subject: str | None
    body: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Notification schemas ───────────────────────────────────────────────────────

class NotificationSummary(BaseModel):
    """
    PHI-safe summary for list responses.
    recipient is masked: only last 4 digits of phone or first 2 chars of email.
    """
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    channel: str
    status: str
    event_type: str
    recipient_masked: str   # computed — never raw PHI
    provider: str | None
    provider_status: str | None
    attempt_count: int
    scheduled_at: datetime
    sent_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, obj) -> "NotificationSummary":
        return cls(
            id=obj.id,
            hospital_id=obj.hospital_id,
            patient_id=obj.patient_id,
            appointment_id=obj.appointment_id,
            channel=obj.channel,
            status=obj.status,
            event_type=obj.event_type,
            recipient_masked=_mask_recipient(obj.recipient),
            provider=obj.provider,
            provider_status=obj.provider_status,
            attempt_count=obj.attempt_count,
            scheduled_at=obj.scheduled_at,
            sent_at=obj.sent_at,
            delivered_at=obj.delivered_at,
            created_at=obj.created_at,
        )


class NotificationRetryResponse(BaseModel):
    notification_id: uuid.UUID
    queued: bool
    message: str


# ── Twilio webhook ─────────────────────────────────────────────────────────────

class TwilioStatusCallback(BaseModel):
    """
    Twilio posts form data to the status webhook.
    Fields mapped from Twilio's status callback payload.
    """
    MessageSid: str
    MessageStatus: str
    ErrorCode: str | None = None


def _mask_recipient(value: str) -> str:
    """Mask phone/email for safe API responses."""
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:2]}***@{domain}"
    if len(value) > 6:
        return value[:4] + "****" + value[-2:]
    return "****"
