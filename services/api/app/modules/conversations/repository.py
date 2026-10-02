"""
Conversation repository — tenant-scoped data access.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MessageRole
from app.modules.conversations.models import Conversation, ConversationMessage


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Conversation ───────────────────────────────────────────────────────────

    async def get_by_id(
        self, conversation_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Conversation | None:
        result = await self._db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_with_messages(
        self, conversation_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Conversation | None:
        result = await self._db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Conversation], int]:
        base_q = select(Conversation).where(Conversation.hospital_id == hospital_id)
        if patient_id:
            base_q = base_q.where(Conversation.patient_id == patient_id)
        if status:
            base_q = base_q.where(Conversation.status == status)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()

        items_q = (
            base_q.order_by(Conversation.started_at.desc())
            .limit(limit).offset(offset)
        )
        items = list((await self._db.execute(items_q)).scalars().all())
        return items, total

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> Conversation:
        conv = Conversation(hospital_id=hospital_id, **fields)
        self._db.add(conv)
        await self._db.flush()
        await self._db.refresh(conv)
        return conv

    async def update(
        self,
        conversation_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> Conversation | None:
        await self._db.execute(
            update(Conversation)
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(conversation_id, hospital_id)

    # ── Messages ───────────────────────────────────────────────────────────────

    async def create_message(
        self,
        conversation_id: uuid.UUID,
        hospital_id: uuid.UUID,
        **fields: Any,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            hospital_id=hospital_id,
            **fields,
        )
        self._db.add(msg)
        await self._db.flush()
        await self._db.refresh(msg)

        # Bump last_message_at on conversation
        await self._db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=datetime.now(UTC))
        )
        return msg

    async def get_message_count(self, conversation_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.count()).where(
                and_(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role != MessageRole.TOOL.value,
                )
            )
        )
        return result.scalar_one() or 0

    async def get_chat_history(
        self,
        conversation_id: uuid.UUID,
        *,
        max_turns: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Returns the last `max_turns` USER and ASSISTANT messages as dicts
        suitable for the GeminiGateway._build_gemini_history() method.
        TOOL messages are excluded from LLM context (they're only for audit).
        """
        result = await self._db.execute(
            select(ConversationMessage)
            .where(
                and_(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.role.in_([
                        MessageRole.USER.value,
                        MessageRole.ASSISTANT.value,
                    ]),
                )
            )
            .order_by(ConversationMessage.created_at.desc())
            .limit(max_turns)
        )
        messages = list(reversed(result.scalars().all()))  # chronological order

        return [
            {
                "role": msg.role.lower(),  # "user" or "assistant"
                "content": msg.content,
            }
            for msg in messages
        ]
