"""
Appointment ORM model.

Critical constraints:
- Double-booking prevented by DB partial unique index:
    UNIQUE (doctor_id, scheduled_at) WHERE status NOT IN ('CANCELLED', 'RESCHEDULED')
- This constraint is the ultimate safety net even under concurrent requests.

PHI note: chief_complaint and notes may contain clinical text.
They must NEVER appear in audit log state diffs.
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import AppointmentSource, AppointmentStatus, AppointmentType


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single patient appointment with a doctor.

    Status lifecycle:
        PENDING → CONFIRMED → COMPLETED
                           → NO_SHOW
                           → CANCELLED  (sets cancelled_at, cancellation_reason)
        CONFIRMED → RESCHEDULED (new appointment created, this one archived)

    The double-booking guard lives at the DB level:
        UNIQUE (doctor_id, scheduled_at) WHERE status NOT IN ('CANCELLED', 'RESCHEDULED')

    See migration 004_appointments.py for the partial index definition.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_doctor_id_scheduled", "doctor_id", "scheduled_at"),
        Index("ix_appointments_patient_id", "patient_id"),
        Index("ix_appointments_hospital_status", "hospital_id", "status"),
        Index("ix_appointments_scheduled_at", "scheduled_at"),
        Index("ix_appointments_hospital_date", "hospital_id", "scheduled_at"),
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
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Slot timestamps (UTC)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=20)

    status: Mapped[AppointmentStatus] = mapped_column(
        String(20), nullable=False, default=AppointmentStatus.CONFIRMED
    )
    appointment_type: Mapped[AppointmentType] = mapped_column(
        String(20), nullable=False, default=AppointmentType.OPD
    )
    source: Mapped[AppointmentSource] = mapped_column(
        String(20), nullable=False, default=AppointmentSource.WEB
    )

    # Phase 4 link: conversation that triggered this booking
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Clinical context (PHI — never log)
    notes: Mapped[str | None] = mapped_column(Text)
    chief_complaint: Mapped[str | None] = mapped_column(
        Text, comment="Patient-reported reason for visit — PHI"
    )

    # Cancellation fields
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Reschedule chain
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
    )

    # Walk-in queue token
    token_number: Mapped[int | None] = mapped_column(SmallInteger)

    # ── Relationships ──────────────────────────────────────────────────────────
    patient: Mapped["Patient"] = relationship("Patient", lazy="select")     # type: ignore[name-defined]
    doctor: Mapped["Doctor"] = relationship("Doctor", lazy="select")        # type: ignore[name-defined]
    department: Mapped["Department"] = relationship("Department", lazy="select")  # type: ignore[name-defined]
    rescheduled_from: Mapped["Appointment | None"] = relationship(
        "Appointment",
        remote_side="Appointment.id",
        lazy="select",
        foreign_keys=[rescheduled_from_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} doctor={self.doctor_id} "
            f"patient={self.patient_id} at={self.scheduled_at} status={self.status}>"
        )
