"""
Notification ORM models.

notification_templates: hospital-configurable per-channel, per-event templates
notifications: individual delivery records (one per channel per event)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A hospital-owned notification template.

    Unique per (hospital_id, event_type, channel, language).
    DEFAULT templates are seeded when a hospital is created.
    Hospitals can customise or override any default template.

    Jinja2 syntax: {{ patient_name }}, {{ appointment_date }}, etc.
    """

    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint(
            "hospital_id", "event_type", "channel", "language",
            name="uq_notification_templates_key",
        ),
        Index("ix_notif_templates_hospital_id", "hospital_id"),
        Index("ix_notif_templates_event_type", "event_type"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # appointment.confirmed, appointment.reminder_24h, appointment.reminder_2h,
    # appointment.cancelled, appointment.rescheduled, appointment.completed,
    # conversation.escalated
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # SMS, WHATSAPP, EMAIL, PUSH
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # BCP-47 language tag — en, hi, ta, etc.
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # Subject line — EMAIL only, null for SMS/WhatsApp
    subject: Mapped[str | None] = mapped_column(String(500))
    # Jinja2 template body
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationTemplate event={self.event_type} "
            f"channel={self.channel} lang={self.language}>"
        )


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single notification delivery record.

    Lifecycle:
      PENDING → (dispatched) → SENT → (webhook) → DELIVERED
                             → FAILED → (retried) → SENT | FAILED
      PENDING → CANCELLED (if appointment cancelled before delivery)

    PHI note:
      `recipient` and `body` contain PHI (phone/email, patient name).
      They are MASKED in API responses.
      They are NEVER written to audit_logs.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_hospital_id", "hospital_id"),
        Index("ix_notifications_patient_id", "patient_id"),
        Index("ix_notifications_appointment_id", "appointment_id"),
        Index("ix_notifications_status", "status"),
        # Worker query: PENDING notifications ready to send
        Index(
            "ix_notifications_pending_scheduled",
            "status", "scheduled_at",
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
    )

    # Channel + status
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # PHI — masked in responses
    recipient: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="PHI — phone or email"
    )
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(
        Text, nullable=False, comment="PHI — rendered template with patient data"
    )

    # Delivery metadata
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    provider_status: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} channel={self.channel} "
            f"event={self.event_type} status={self.status}>"
        )
