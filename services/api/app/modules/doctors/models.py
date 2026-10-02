"""
Doctor and DoctorDepartment ORM models.

Doctor: clinical staff member belonging to a hospital.
DoctorDepartment: many-to-many between doctors and departments,
                  with is_primary flag and audit timestamp.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import DoctorStatus


class DoctorDepartment(Base):
    """
    Association between a doctor and a department.
    Carries is_primary to designate the doctor's primary department.
    Uses a composite primary key (doctor_id, department_id).
    """

    __tablename__ = "doctor_departments"
    __table_args__ = (
        Index("ix_doctor_departments_department_id", "department_id"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="department_links")
    department: Mapped["Department"] = relationship(  # type: ignore[name-defined]
        "Department", back_populates="doctor_links"
    )

    def __repr__(self) -> str:
        return (
            f"<DoctorDepartment doctor={self.doctor_id} dept={self.department_id} "
            f"primary={self.is_primary}>"
        )


class Doctor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Doctor profile within a hospital.
    Optionally linked to a User account via user_id for authentication.
    Financial amounts are stored in paise (smallest INR unit) to avoid float precision issues.
    """

    __tablename__ = "doctors"
    __table_args__ = (
        Index("ix_doctors_hospital_id", "hospital_id"),
        Index("ix_doctors_user_id", "user_id"),
        Index("ix_doctors_hospital_status", "hospital_id", "status"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Optional link to user account (for doctor login)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(
        String(100), comment="Medical Council of India / NMC registration number"
    )
    specialization: Mapped[str | None] = mapped_column(String(255))
    qualifications: Mapped[str | None] = mapped_column(Text)

    # Stored in paise (1 INR = 100 paise) to avoid floating-point issues
    consultation_fee_paise: Mapped[int | None] = mapped_column(
        BigInteger, comment="Consultation fee in paise (100 paise = 1 INR)"
    )

    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)

    status: Mapped[DoctorStatus] = mapped_column(
        String(20), nullable=False, default=DoctorStatus.ACTIVE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", lazy="select")  # type: ignore[name-defined]
    user: Mapped["User | None"] = relationship("User", lazy="select")  # type: ignore[name-defined]
    department_links: Mapped[list[DoctorDepartment]] = relationship(
        "DoctorDepartment",
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="selectin",  # always load with doctor
    )

    @property
    def consultation_fee_inr(self) -> float | None:
        """Convenience property returning fee in INR."""
        if self.consultation_fee_paise is None:
            return None
        return self.consultation_fee_paise / 100

    @property
    def primary_department_id(self) -> uuid.UUID | None:
        """Returns the department_id marked as primary, or None."""
        for link in self.department_links:
            if link.is_primary:
                return link.department_id
        return None

    @property
    def department_ids(self) -> list[uuid.UUID]:
        return [link.department_id for link in self.department_links]

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name={self.full_name} hospital={self.hospital_id}>"
