"""006 notifications — notification_templates and notifications tables

Revision ID: 006
Revises: 005
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── notification_templates ─────────────────────────────────────────────────
    op.create_table(
        "notification_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hospital_id", UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("hospital_id", "event_type", "channel", "language", name="uq_notification_templates_key"),
    )
    op.create_index("ix_notif_templates_hospital_id", "notification_templates", ["hospital_id"])
    op.create_index("ix_notif_templates_event_type", "notification_templates", ["event_type"])
    op.execute("""
        CREATE TRIGGER trg_notification_templates_updated_at
        BEFORE UPDATE ON notification_templates
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ── notifications ──────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hospital_id", UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        # Classification
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("event_type", sa.String(50), nullable=False),
        # PHI columns
        sa.Column("recipient", sa.String(255), nullable=False, comment="PHI — phone or email"),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text, nullable=False, comment="PHI — rendered notification body"),
        # Delivery tracking
        sa.Column("provider", sa.String(50)),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("provider_status", sa.String(100)),
        sa.Column("error_message", sa.Text),
        sa.Column("attempt_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.SmallInteger, nullable=False, server_default="3"),
        # Scheduling
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_notifications_hospital_id", "notifications", ["hospital_id"])
    op.create_index("ix_notifications_patient_id", "notifications", ["patient_id"])
    op.create_index("ix_notifications_appointment_id", "notifications", ["appointment_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    # Worker index: PENDING notifications by scheduled_at
    op.create_index("ix_notifications_pending_scheduled", "notifications", ["status", "scheduled_at"])
    # Twilio webhook lookup: provider_message_id
    op.create_index("ix_notifications_provider_message_id", "notifications", ["provider_message_id"])
    op.execute("""
        CREATE TRIGGER trg_notifications_updated_at
        BEFORE UPDATE ON notifications
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_notifications_updated_at ON notifications")
    op.execute("DROP TRIGGER IF EXISTS trg_notification_templates_updated_at ON notification_templates")
    op.drop_table("notifications")
    op.drop_table("notification_templates")
