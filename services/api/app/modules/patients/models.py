"""
Patient ORM model.

Patients are a SEPARATE entity from Users (clinical vs authentication separation).
Keeps PHI (Protected Health Information) isolated from the auth/staff user table.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import BloodGroup, Gender


class Patient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Represents a patient in a hospital.

    MRN (Medical Record Number) is optional but unique per hospital when set.
    PHI fields: full_name, phone, email, date_of_birth, gender, blood_group.

    IMPORTANT: PHI must never appear in audit log before_state/after_state.
    Use only patient_id in audit records.
    """

    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("hospital_id", "mrn", name="uq_patients_hospital_mrn"),
        Index("ix_patients_hospital_id", "hospital_id"),
        Index("ix_patients_hospital_mrn", "hospital_id", "mrn"),
        Index("ix_patients_phone", "phone"),
        Index("ix_patients_email", "email"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Medical Record Number — hospital-assigned, unique per hospital
    mrn: Mapped[str | None] = mapped_column(
        String(100),
        comment="Medical Record Number — unique per hospital when set",
    )

    # ── PHI fields ────────────────────────────────────────────────────────────
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    blood_group: Mapped[str | None] = mapped_column(String(5))

    # ── Preferences and context ───────────────────────────────────────────────
    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )

    # JSONB: {name, relationship, phone}
    emergency_contact: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # JSONB: {line1, line2, city, state, pincode}
    address: Mapped[dict | None] = mapped_column(JSONB)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", lazy="select")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Patient id={self.id} mrn={self.mrn} hospital={self.hospital_id}>"
