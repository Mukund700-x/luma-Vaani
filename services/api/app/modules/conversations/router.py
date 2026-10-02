"""
Conversations API router — /api/v1/hospitals/{hospital_id}/conversations
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.enums import ConversationStatus
from app.core.pagination import Page, PaginationDep
from app.modules.conversations.schemas import (
    AITurnResponse,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationStart,
    ConversationSummary,
    SendMessageRequest,
)
from app.modules.conversations.service import ConversationService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/conversations",
    tags=["Conversations (AI)"],
)


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=201,
    summary="Start conversation",
    description=(
        "Open a new AI conversation session. "
        "Returns a `conversation_id` to use for subsequent message turns. "
        "One session may contain many message turns. "
        "Optional `patient_id` pre-identifies the patient (for logged-in patient portals). "
        "For anonymous channels (WhatsApp, kiosk), omit `patient_id` — the AI will identify "
        "the patient via the `find_patient` tool."
    ),
)
async def start_conversation(
    hospital_id: HospitalPathDep,
    payload: ConversationStart,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    return await ConversationService(db).start_conversation(
        hospital_id, payload, actor=current_user
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=AITurnResponse,
    summary="Send message",
    description=(
        "**Send a patient message and receive the AI response.** "
        "This is the primary real-time endpoint for the patient chat experience. "
        "\n\n"
        "The pipeline per call:\n"
        "1. Safety check on input (emergency detection)\n"
        "2. AI (Gemini) processes the message with tool access\n"
        "3. Safety check on AI output (prohibited content detection)\n"
        "4. Full tool call audit trail persisted\n"
        "\n"
        "If `is_emergency=true` in the response, display the emergency escalation "
        "message prominently and offer to call emergency services. "
        "If `escalate_to_human=true`, surface a 'Talk to receptionist' option."
    ),
)
async def send_message(
    hospital_id: HospitalPathDep,
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AITurnResponse:
    return await ConversationService(db).send_message(
        conversation_id, hospital_id, payload, actor=current_user
    )


@router.post(
    "/{conversation_id}/end",
    response_model=ConversationResponse,
    summary="End conversation",
    description="Mark the conversation as ENDED. No further messages accepted after this.",
)
async def end_conversation(
    hospital_id: HospitalPathDep,
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    return await ConversationService(db).end_conversation(
        conversation_id, hospital_id, actor=current_user
    )


# ── Admin / Staff views ────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=Page[ConversationSummary],
    summary="List conversations",
    description="**RECEPTIONIST or above.** Paginated conversation inbox for the hospital.",
)
async def list_conversations(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    patient_id: uuid.UUID | None = Query(default=None),
    status: ConversationStatus | None = Query(default=None),
) -> Page[ConversationSummary]:
    return await ConversationService(db).list_conversations(
        hospital_id, current_user, params=params,
        patient_id=patient_id, status=status,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail",
    description=(
        "**RECEPTIONIST or above.** Full conversation with all messages "
        "including tool call audit records. Use for patient support and AI quality review."
    ),
)
async def get_conversation_detail(
    hospital_id: HospitalPathDep,
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationDetailResponse:
    return await ConversationService(db).get_conversation_detail(
        conversation_id, hospital_id, actor=current_user
    )
