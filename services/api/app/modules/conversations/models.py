"""
Conversation and ConversationMessage ORM models.

Conversation: a single patient session (may span multiple messages).
ConversationMessage: one turn in the conversation (user, assistant, or tool record).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDPrimaryKeyMixin
from app.core.enums import ConversationChannel, ConversationStatus, MessageRole


class Conversation(Base, UUIDPrimaryKeyMixin):
    """
    A patient conversation session.

    One session covers the full patient interaction (multi-turn).
    patient_id may be null initially — set by find_patient tool.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_hospital_id", "hospital_id"),
        Index("ix_conversations_patient_id", "patient_id"),
        Index("ix_conversations_hospital_status", "hospital_id", "status"),
        Index("ix_conversations_started_at", "started_at"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # May be null at conversation start; populated by find_patient tool
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="SET NULL"),
    )

    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConversationChannel.WEB.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConversationStatus.ACTIVE.value
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )

    # Accumulated conversation context (intent, collected slots, etc.)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Channel-specific metadata (WhatsApp phone, session ID, etc.)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        order_by="ConversationMessage.created_at.asc()",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} channel={self.channel} "
            f"status={self.status} hospital={self.hospital_id}>"
        )


class ConversationMessage(Base, UUIDPrimaryKeyMixin):
    """
    A single message in a conversation.

    Roles:
    - USER: patient message
    - ASSISTANT: AI text response
    - TOOL: tool invocation record (tool_name, tool_input, tool_output in metadata)
    - SYSTEM: system-generated events (e.g., session start, patient identified)
    """

    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_conv_messages_conversation_id", "conversation_id"),
        Index("ix_conv_messages_hospital_id", "hospital_id"),
        Index("ix_conv_messages_created_at", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Tool-specific fields (only populated when role=TOOL)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    tool_input: Mapped[dict | None] = mapped_column(JSONB)
    tool_output: Mapped[dict | None] = mapped_column(JSONB)

    # Metadata: tokens, latency, safety flags, etc.
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationMessage id={self.id} role={self.role} "
            f"conversation={self.conversation_id}>"
        )
