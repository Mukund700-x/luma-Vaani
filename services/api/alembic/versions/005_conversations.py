"""005 conversations — conversations and conversation_messages tables

Revision ID: 005
Revises: 004
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations ──────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False,
        ),
        # May be null initially — populated by find_patient tool
        sa.Column(
            "patient_id", UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True,
        ),
        # WEB, VOICE, WHATSAPP
        sa.Column("channel", sa.String(20), nullable=False, server_default="WEB"),
        # ACTIVE, ENDED, ESCALATED
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        # BCP-47 language tag
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        # Accumulated conversation context (intent, collected slots, etc.)
        sa.Column("context", JSONB, nullable=False, server_default="{}"),
        # Channel-specific metadata
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_conversations_hospital_id", "conversations", ["hospital_id"])
    op.create_index("ix_conversations_patient_id", "conversations", ["patient_id"])
    op.create_index(
        "ix_conversations_hospital_status", "conversations", ["hospital_id", "status"]
    )
    op.create_index("ix_conversations_started_at", "conversations", ["started_at"])

    # ── conversation_messages ──────────────────────────────────────────────────
    op.create_table(
        "conversation_messages",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id", UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False,
        ),
        # Denormalized for fast per-hospital queries
        sa.Column(
            "hospital_id", UUID(as_uuid=True),
            sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False,
        ),
        # USER, ASSISTANT, TOOL, SYSTEM
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # TOOL-specific columns (null for USER/ASSISTANT)
        sa.Column("tool_name", sa.String(100)),
        sa.Column("tool_input", JSONB),
        sa.Column("tool_output", JSONB),
        # metadata: tokens, latency, safety_flags, etc.
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "ix_conv_messages_conversation_id", "conversation_messages", ["conversation_id"]
    )
    op.create_index(
        "ix_conv_messages_hospital_id", "conversation_messages", ["hospital_id"]
    )
    op.create_index(
        "ix_conv_messages_created_at", "conversation_messages", ["created_at"]
    )

    # Partial index: fast lookup of TOOL records for audit queries
    op.execute("""
        CREATE INDEX ix_conv_messages_tool_records
        ON conversation_messages (conversation_id, tool_name)
        WHERE role = 'TOOL';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conv_messages_tool_records")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
