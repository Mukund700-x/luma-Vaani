"""
AuditLog ORM model — immutable audit trail for all important actions.
"""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, UUIDPrimaryKeyMixin
from app.core.enums import AuditActorType

from datetime import UTC, datetime
from sqlalchemy import DateTime


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """
    Immutable audit record. Never update or delete these rows.
    Sensitive content must NOT be stored in before_state / after_state.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_hospital_id_timestamp", "hospital_id", "timestamp"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_actor", "actor_type", "actor_id"),
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[AuditActorType] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))  # user_id / "system" / worker name

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))

    # Structured metadata — do NOT store raw PII or PHI
    before_state: Mapped[dict | None] = mapped_column(JSONB)
    after_state: Mapped[dict | None] = mapped_column(JSONB)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} actor={self.actor_type}:{self.actor_id}>"
