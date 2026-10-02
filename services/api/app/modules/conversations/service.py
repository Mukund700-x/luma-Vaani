"""
Conversation service — orchestrates the full AI pipeline per message turn.

Pipeline per send_message() call:
  1. Load conversation + verify it's ACTIVE
  2. Enforce turn limit (prevent abuse)
  3. SafetyLayer: check patient input for emergencies
  4. If emergency → return escalation response without calling LLM
  5. Persist patient message to DB
  6. Build hospital-specific system prompt
  7. Load conversation history (last N turns)
  8. Build ToolContext + ToolRegistry
  9. GeminiGateway: run agentic loop (LLM + tools)
  10. SafetyLayer: check AI output for prohibited content
  11. Persist tool call records (audit trail)
  12. Persist AI response message
  13. Propagate context updates (patient_id from find_patient tool)
  14. Audit log the full turn
  15. Return AITurnResponse
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.gateway import GeminiGateway
from app.ai.prompts.system_prompt import SystemPromptBuilder
from app.ai.safety.safety_layer import SafetyLayer
from app.ai.tools.base import ToolContext, build_default_registry
from app.core.audit import AuditService
from app.core.config import settings
from app.core.enums import (
    AuditActorType,
    ConversationChannel,
    ConversationStatus,
    MessageRole,
    UserRole,
)
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.conversations.models import Conversation
from app.modules.conversations.repository import ConversationRepository
from app.modules.conversations.schemas import (
    AITurnResponse,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationStart,
    ConversationSummary,
    MessageResponse,
    SendMessageRequest,
)
from app.modules.hospitals.repository import HospitalRepository

logger = structlog.get_logger(__name__)

_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.HOSPITAL_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
}

_EMERGENCY_SYSTEM_MESSAGE = MessageRole.ASSISTANT


class ConversationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ConversationRepository(db)
        self._audit = AuditService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_conv_or_404(
        self, conversation_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Conversation:
        conv = await self._repo.get_by_id(conversation_id, hospital_id)
        if not conv:
            raise NotFoundException("Conversation", str(conversation_id))
        return conv

    async def _get_hospital(self, hospital_id: uuid.UUID) -> Any:
        hospital = await HospitalRepository(self._db).get_by_id(hospital_id)
        if not hospital:
            raise NotFoundException("Hospital", str(hospital_id))
        return hospital

    # ── Conversation lifecycle ─────────────────────────────────────────────────

    async def start_conversation(
        self,
        hospital_id: uuid.UUID,
        payload: ConversationStart,
        actor: User,
    ) -> ConversationResponse:
        """Start a new conversation session."""
        conv = await self._repo.create(
            hospital_id,
            patient_id=payload.patient_id,
            channel=payload.channel.value,
            status=ConversationStatus.ACTIVE.value,
            language=payload.language,
            context={},
            metadata={"started_by": str(actor.id)},
        )

        await self._audit.log(
            action="conversation.start",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="conversation",
            resource_id=str(conv.id),
            after_state={"channel": conv.channel, "language": conv.language},
        )
        logger.info("conversation_started", conversation_id=str(conv.id), hospital_id=str(hospital_id))
        return ConversationResponse.model_validate(conv)

    async def end_conversation(
        self,
        conversation_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> ConversationResponse:
        conv = await self._get_conv_or_404(conversation_id, hospital_id)
        if conv.status != ConversationStatus.ACTIVE.value:
            raise ConflictException(f"Conversation is already {conv.status}")

        updated = await self._repo.update(
            conversation_id, hospital_id,
            {"status": ConversationStatus.ENDED.value, "ended_at": datetime.now(UTC)},
        )
        return ConversationResponse.model_validate(updated)

    # ── Core: send a message through the AI pipeline ──────────────────────────

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: SendMessageRequest,
        actor: User,
    ) -> AITurnResponse:
        """Process one patient message turn through the full AI pipeline."""

        # ── 1. Load and validate conversation ─────────────────────────────────
        conv = await self._get_conv_or_404(conversation_id, hospital_id)
        if conv.status != ConversationStatus.ACTIVE.value:
            raise ConflictException("This conversation has ended. Start a new one.")

        # ── 2. Turn limit guard ────────────────────────────────────────────────
        turn_count = await self._repo.get_message_count(conversation_id)
        if turn_count >= settings.AI_MAX_CONVERSATION_TURNS:
            raise ConflictException(
                "Maximum conversation length reached. Please start a new conversation."
            )

        # ── 3. Load hospital ───────────────────────────────────────────────────
        hospital = await self._get_hospital(hospital_id)
        hospital_config: dict = hospital.config or {}
        emergency_number = hospital_config.get("emergency_phone", "112")

        # ── 4. Input safety check ──────────────────────────────────────────────
        safety = SafetyLayer(emergency_number=emergency_number)
        input_check = safety.check_input(payload.content)

        if input_check.is_emergency:
            # Save patient message + emergency response — bypass LLM entirely
            await self._repo.create_message(
                conversation_id, hospital_id,
                role=MessageRole.USER.value,
                content=payload.content,
                metadata={},
            )
            emergency_msg = await self._repo.create_message(
                conversation_id, hospital_id,
                role=MessageRole.ASSISTANT.value,
                content=input_check.emergency_response,
                metadata={"safety_flags": ["emergency_detected_in_input"], "fallback": True},
            )
            logger.warning(
                "emergency_detected",
                conversation_id=str(conversation_id),
                flags=input_check.flags,
            )
            return AITurnResponse(
                conversation_id=conversation_id,
                message=MessageResponse.model_validate(emergency_msg),
                safety_flags=input_check.flags,
                is_emergency=True,
                escalate_to_human=True,
            )

        # ── 5. Persist patient message ─────────────────────────────────────────
        await self._repo.create_message(
            conversation_id, hospital_id,
            role=MessageRole.USER.value,
            content=payload.content,
            metadata={},
        )

        # ── 6. Build system prompt ─────────────────────────────────────────────
        system_prompt = SystemPromptBuilder().build(
            hospital_name=hospital.name,
            hospital_config=hospital_config,
            language=conv.language,
        )

        # ── 6b. RAG: retrieve relevant hospital knowledge ──────────────────────
        # Append semantically-retrieved context to the system prompt so the AI
        # can answer hospital-specific questions (FAQs, policies, hours, etc.)
        # without hallucinating. Non-fatal — proceeds without context on failure.
        try:
            from app.ai.knowledge.embeddings import EmbeddingService
            from app.ai.knowledge.retriever import KnowledgeRetriever
            emb_svc = EmbeddingService(api_key=settings.GEMINI_API_KEY or "")
            if emb_svc.is_available:
                retriever = KnowledgeRetriever(
                    db=self._db,
                    embedding_service=emb_svc,
                    top_k=settings.KNOWLEDGE_TOP_K,
                    min_similarity=settings.KNOWLEDGE_MIN_SIMILARITY,
                )
                rag_results = await retriever.search(
                    hospital_id=hospital_id,
                    query=payload.content,
                    access_scope="PUBLIC",
                )
                if rag_results:
                    rag_context = KnowledgeRetriever.format_for_llm(rag_results)
                    system_prompt = system_prompt + "\n\n" + rag_context
        except Exception:
            logger.debug("rag_retrieval_skipped", conversation_id=str(conversation_id))

        # ── 7. Load conversation history ───────────────────────────────────────
        history = await self._repo.get_chat_history(
            conversation_id, max_turns=settings.AI_MAX_CONVERSATION_TURNS
        )

        # ── 8. Build tool context ──────────────────────────────────────────────
        tool_context = ToolContext(
            hospital_id=hospital_id,
            conversation_id=conversation_id,
            patient_id=conv.patient_id,
            db=self._db,
            hospital_config=hospital_config,
        )
        registry = build_default_registry(
            timeout_seconds=settings.AI_TOOL_TIMEOUT_SECONDS
        )

        # ── 9. Run Gemini agentic loop ─────────────────────────────────────────
        gateway = GeminiGateway(
            api_key=settings.GEMINI_API_KEY or "",
            model_name=settings.GEMINI_MODEL,
        )
        gateway_response = await gateway.run(
            system_prompt=system_prompt,
            history=history,
            user_message=payload.content,
            context=tool_context,
            registry=registry,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            max_iterations=settings.AI_MAX_TOOL_ITERATIONS,
        )

        # ── 10. Output safety check ────────────────────────────────────────────
        output_check = safety.check_output(gateway_response.text)
        final_text = output_check.cleaned_text
        all_flags = input_check.flags + output_check.flags + gateway_response.safety_flags

        # ── 11. Persist tool call records (audit trail) ────────────────────────
        for tc in gateway_response.tool_calls:
            await self._repo.create_message(
                conversation_id, hospital_id,
                role=MessageRole.TOOL.value,
                content=tc.get("name", "unknown_tool"),
                tool_name=tc.get("name"),
                tool_input=tc.get("input"),
                tool_output=tc.get("output"),
                metadata={"executed_at": tc.get("executed_at")},
            )

        # ── 12. Persist AI response ────────────────────────────────────────────
        ai_msg = await self._repo.create_message(
            conversation_id, hospital_id,
            role=MessageRole.ASSISTANT.value,
            content=final_text,
            metadata={
                "safety_flags": all_flags,
                "tool_calls_made": len(gateway_response.tool_calls),
                "gateway_iterations": gateway_response.iterations,
                "fallback_used": gateway_response.fallback_used,
            },
        )

        # ── 13. Propagate context updates (patient_id from find_patient) ───────
        if tool_context._updates:
            await self._repo.update(conversation_id, hospital_id, tool_context._updates)

        # ── 14. Audit ──────────────────────────────────────────────────────────
        await self._audit.log(
            action="conversation.turn",
            actor_type=AuditActorType.AI,
            actor_id="gemini",
            hospital_id=hospital_id,
            resource_type="conversation",
            resource_id=str(conversation_id),
            metadata={
                "turn_count": turn_count + 1,
                "tool_calls": len(gateway_response.tool_calls),
                "safety_flags": all_flags,
                "fallback_used": gateway_response.fallback_used,
            },
        )

        logger.info(
            "conversation_turn_complete",
            conversation_id=str(conversation_id),
            tool_calls=len(gateway_response.tool_calls),
            safety_flags=all_flags,
            fallback=gateway_response.fallback_used,
        )

        return AITurnResponse(
            conversation_id=conversation_id,
            message=MessageResponse.model_validate(ai_msg),
            safety_flags=all_flags,
            tool_calls_made=len(gateway_response.tool_calls),
            is_emergency=output_check.is_emergency,
            escalate_to_human=output_check.is_emergency or gateway_response.fallback_used,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_conversations(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        *,
        params: PageParams,
        patient_id: uuid.UUID | None = None,
        status: ConversationStatus | None = None,
    ) -> Page[ConversationSummary]:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required to view conversations")

        items, total = await self._repo.list(
            hospital_id,
            patient_id=patient_id,
            status=status.value if status else None,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [ConversationSummary.model_validate(c) for c in items],
            total, params,
        )

    async def get_conversation_detail(
        self,
        conversation_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> ConversationDetailResponse:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required to view conversation details")

        conv = await self._repo.get_with_messages(conversation_id, hospital_id)
        if not conv:
            raise NotFoundException("Conversation", str(conversation_id))
        return ConversationDetailResponse.model_validate(conv)
