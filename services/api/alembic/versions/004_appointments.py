"""004 appointments — appointments table with double-booking guard

Revision ID: 004
Revises: 003
Create Date: 2026-10-02

Critical index:
    UNIQUE (doctor_id, scheduled_at) WHERE status NOT IN ('CANCELLED', 'RESCHEDULED')

This partial unique index is the database-level double-booking guard.
Even if two concurrent API requests pass the engine's availability check,
only one INSERT will succeed. The other raises IntegrityError, which the
service layer converts to HTTP 409 ConflictException.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Tenant key
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False,
        ),
        # Parties
        sa.Column(
            "patient_id", UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "doctor_id", UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "department_id", UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False,
        ),
        # Slot times (UTC)
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.SmallInteger, nullable=False, server_default="20"),
        # Classification
        sa.Column("status", sa.String(20), nullable=False, server_default="CONFIRMED"),
        sa.Column("appointment_type", sa.String(20), nullable=False, server_default="OPD"),
        sa.Column("source", sa.String(20), nullable=False, server_default="WEB"),
        # Phase 4 link
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        # Clinical context (PHI)
        sa.Column("notes", sa.Text),
        sa.Column("chief_complaint", sa.Text, comment="PHI — never log"),
        # Cancellation metadata
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column(
            "cancelled_by_user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        # Reschedule chain
        sa.Column(
            "rescheduled_from_id", UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True,
        ),
        # Walk-in queue token
        sa.Column("token_number", sa.SmallInteger),
        # Timestamps
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )

    # Regular indexes for common queries
    op.create_index(
        "ix_appointments_doctor_id_scheduled",
        "appointments", ["doctor_id", "scheduled_at"],
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index(
        "ix_appointments_hospital_status", "appointments", ["hospital_id", "status"]
    )
    op.create_index("ix_appointments_scheduled_at", "appointments", ["scheduled_at"])
    op.create_index(
        "ix_appointments_hospital_date", "appointments", ["hospital_id", "scheduled_at"]
    )
    op.create_index(
        "ix_appointments_conversation_id", "appointments", ["conversation_id"]
    )

    # ── DOUBLE-BOOKING GUARD ──────────────────────────────────────────────────
    # Partial unique index: only active appointments count.
    # CANCELLED and RESCHEDULED appointments don't block slot reuse.
    # This is the ultimate safety net for concurrent booking attempts.
    op.execute("""
        CREATE UNIQUE INDEX uq_appointments_doctor_slot
        ON appointments (doctor_id, scheduled_at)
        WHERE status NOT IN ('CANCELLED', 'RESCHEDULED');
    """)

    # updated_at auto-trigger
    op.execute("""
        CREATE TRIGGER trg_appointments_updated_at
        BEFORE UPDATE ON appointments
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_appointments_updated_at ON appointments")
    op.execute("DROP INDEX IF EXISTS uq_appointments_doctor_slot")
    op.drop_table("appointments")
