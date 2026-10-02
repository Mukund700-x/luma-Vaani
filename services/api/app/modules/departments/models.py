"""
Department ORM model.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A clinical or administrative department within a hospital.
    Slug is unique per hospital (enforced by DB unique constraint and model).
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("hospital_id", "slug", name="uq_departments_hospital_slug"),
        Index("ix_departments_hospital_id", "hospital_id"),
        Index("ix_departments_hospital_slug", "hospital_id", "slug"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # UI display helpers
    color: Mapped[str | None] = mapped_column(String(7))   # hex e.g. #4A90E2
    icon: Mapped[str | None] = mapped_column(String(50))   # icon key e.g. "heart"

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", lazy="select")  # type: ignore[name-defined]
    doctor_links: Mapped[list["DoctorDepartment"]] = relationship(  # type: ignore[name-defined]
        "DoctorDepartment", back_populates="department", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} slug={self.slug} hospital={self.hospital_id}>"
