"""
Conversation Pydantic schemas.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ConversationChannel, ConversationStatus, MessageRole


# ── Conversation schemas ────────────────────────────────────────────────────────

class ConversationStart(BaseModel):
    channel: ConversationChannel = Field(default=ConversationChannel.WEB)
    language: str = Field(default="en", max_length=10, description="BCP-47 language tag")
    # Optional: supply patient_id if known at conversation start (e.g., logged-in patient)
    patient_id: uuid.UUID | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID | None
    channel: ConversationChannel
    status: ConversationStatus
    language: str
    started_at: datetime
    ended_at: datetime | None
    last_message_at: datetime | None
    context: dict[str, Any]
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID | None
    channel: ConversationChannel
    status: ConversationStatus
    language: str
    started_at: datetime
    last_message_at: datetime | None

    model_config = {"from_attributes": True}


# ── Message schemas ─────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="Patient's message text",
    )


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    tool_name: str | None = None
    # tool_input/output omitted from standard response (only in admin views)
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AITurnResponse(BaseModel):
    """
    Response to a patient message — wraps the AI reply with conversation context.
    """
    conversation_id: uuid.UUID
    message: MessageResponse           # the AI's reply
    safety_flags: list[str] = Field(default_factory=list)
    tool_calls_made: int = 0
    is_emergency: bool = False
    escalate_to_human: bool = False


# ── Admin views ─────────────────────────────────────────────────────────────────

class MessageDetailResponse(BaseModel):
    """Full message detail including tool call data (admin/staff only)."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    tool_name: str | None
    tool_input: dict[str, Any] | None
    tool_output: dict[str, Any] | None
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    """Full conversation with all messages (admin/staff only)."""
    id: uuid.UUID
    hospital_id: uuid.UUID
    patient_id: uuid.UUID | None
    channel: ConversationChannel
    status: ConversationStatus
    language: str
    started_at: datetime
    ended_at: datetime | None
    messages: list[MessageDetailResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
