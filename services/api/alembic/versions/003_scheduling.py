"""003 scheduling — doctor_schedules and schedule_exceptions tables

Revision ID: 003
Revises: 002
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── doctor_schedules ──────────────────────────────────────────────────────
    op.create_table(
        "doctor_schedules",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "doctor_id", UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False,
        ),
        # 0=Monday … 6=Sunday
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        # Wall-clock local times — AvailabilityEngine applies hospital timezone
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("slot_duration_minutes", sa.SmallInteger, nullable=False, server_default="20"),
        # None = unlimited within the time window
        sa.Column("max_appointments", sa.SmallInteger),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        # Optional validity range
        sa.Column("valid_from", sa.Date),
        sa.Column("valid_until", sa.Date),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("ix_doctor_schedules_doctor_id", "doctor_schedules", ["doctor_id"])
    op.create_index("ix_doctor_schedules_hospital_id", "doctor_schedules", ["hospital_id"])

    # updated_at auto-trigger
    op.execute("""
        CREATE TRIGGER trg_doctor_schedules_updated_at
        BEFORE UPDATE ON doctor_schedules
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ── schedule_exceptions ───────────────────────────────────────────────────
    op.create_table(
        "schedule_exceptions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "doctor_id", UUID(as_uuid=True),
            sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False,
        ),
        # LEAVE, HOLIDAY, BLOCKED, EXTENDED
        sa.Column("exception_type", sa.String(20), nullable=False),
        # UTC datetimes
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("is_all_day", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_by", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "ix_schedule_exceptions_doctor_id", "schedule_exceptions", ["doctor_id"]
    )
    op.create_index(
        "ix_schedule_exceptions_doctor_range",
        "schedule_exceptions",
        ["doctor_id", "start_datetime", "end_datetime"],
    )

    # ── GiST index for fast temporal overlap queries ──────────────────────────
    # Uses tstzrange so the engine's overlap check benefits from index support
    op.execute("""
        CREATE INDEX ix_schedule_exceptions_tstzrange
        ON schedule_exceptions
        USING GIST (tstzrange(start_datetime, end_datetime))
        WHERE exception_type IN ('LEAVE', 'HOLIDAY', 'BLOCKED');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_doctor_schedules_updated_at ON doctor_schedules")
    op.drop_table("schedule_exceptions")
    op.drop_table("doctor_schedules")
