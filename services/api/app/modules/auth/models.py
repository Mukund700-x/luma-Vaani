"""
User ORM model (staff users: admin, receptionist, doctor).
Patients have their own model in the patients module.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import UserRole


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Platform user — covers SUPER_ADMIN, HOSPITAL_ADMIN, RECEPTIONIST, DOCTOR.
    Patients are a separate entity to keep clinical and auth concerns separated.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_hospital_id_email", "hospital_id", "email"),
    )

    # Tenant key — NULL for SUPER_ADMIN only
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(30), nullable=False, default=UserRole.RECEPTIONIST
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    hospital: Mapped["Hospital | None"] = relationship(  # type: ignore[name-defined]
        "Hospital", back_populates="users"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
