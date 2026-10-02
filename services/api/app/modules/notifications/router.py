"""
Notifications API router.

/hospitals/{hid}/notifications          — delivery history
/hospitals/{hid}/notification-templates — template CRUD
/webhooks/twilio/status                 — Twilio delivery callback (public)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.pagination import Page, PaginationDep
from app.modules.notifications.schemas import (
    NotificationRetryResponse,
    NotificationSummary,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
)
from app.modules.notifications.service import NotificationService

router = APIRouter(tags=["Notifications"])

# ── Notification history ───────────────────────────────────────────────────────

@router.get(
    "/hospitals/{hospital_id}/notifications",
    response_model=Page[NotificationSummary],
    summary="List notification history",
    description=(
        "**RECEPTIONIST or above.** Paginated notification history for the hospital. "
        "Recipient is masked in responses (PHI protection). "
        "Filter by patient, appointment, status, or channel."
    ),
)
async def list_notifications(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    patient_id: uuid.UUID | None = Query(default=None),
    appointment_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None, description="PENDING | SENT | FAILED | DELIVERED"),
    channel: str | None = Query(default=None, description="SMS | WHATSAPP | EMAIL"),
) -> Page[NotificationSummary]:
    return await NotificationService(db).list_notifications(
        hospital_id, current_user, params=params,
        patient_id=patient_id, appointment_id=appointment_id,
        status=status, channel=channel,
    )


@router.post(
    "/hospitals/{hospital_id}/notifications/{notification_id}/retry",
    response_model=NotificationRetryResponse,
    summary="Retry notification",
    description=(
        "**RECEPTIONIST or above.** Re-dispatch a FAILED or PENDING notification immediately. "
        "Grants one additional attempt beyond the max_attempts limit."
    ),
)
async def retry_notification(
    hospital_id: HospitalPathDep,
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRetryResponse:
    return await NotificationService(db).retry_notification(
        notification_id, hospital_id, actor=current_user
    )


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get(
    "/hospitals/{hospital_id}/notification-templates",
    response_model=list[NotificationTemplateResponse],
    summary="List notification templates",
    description="**RECEPTIONIST or above.** All templates configured for this hospital.",
)
async def list_templates(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    event_type: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> list[NotificationTemplateResponse]:
    return await NotificationService(db).list_templates(
        hospital_id, current_user, event_type=event_type, channel=channel
    )


@router.post(
    "/hospitals/{hospital_id}/notification-templates",
    response_model=NotificationTemplateResponse,
    status_code=201,
    summary="Create or update template",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** "
        "Creates a new template or updates existing one for the same "
        "(event_type, channel, language) combination. "
        "Template body uses Jinja2 syntax: `{{ patient_name }}`, `{{ appointment_date }}`, etc. "
        "\n\nAvailable variables: `patient_name`, `patient_full_name`, `doctor_name`, "
        "`department`, `hospital_name`, `appointment_date`, `appointment_time`, "
        "`appointment_ref`, `cancellation_reason`, `emergency_number`"
    ),
)
async def upsert_template(
    hospital_id: HospitalPathDep,
    payload: NotificationTemplateCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTemplateResponse:
    return await NotificationService(db).upsert_template(
        hospital_id, payload, actor=current_user
    )


@router.delete(
    "/hospitals/{hospital_id}/notification-templates/{template_id}",
    status_code=204,
    summary="Delete template",
    description="**HOSPITAL_ADMIN or SUPER_ADMIN.** Hard-delete a notification template.",
)
async def delete_template(
    hospital_id: HospitalPathDep,
    template_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await NotificationService(db).delete_template(
        template_id, hospital_id, actor=current_user
    )


@router.post(
    "/hospitals/{hospital_id}/notification-templates/seed",
    response_model=dict,
    summary="Seed default templates",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** "
        "Seeds all built-in default templates (SMS, WhatsApp, Email) for this hospital. "
        "Existing templates are skipped unless `overwrite=true`. "
        "Returns `{'created': N, 'skipped': M}`."
    ),
)
async def seed_default_templates(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    overwrite: bool = Query(default=False, description="Overwrite existing templates"),
) -> dict:
    return await NotificationService(db).seed_default_templates(
        hospital_id, current_user, overwrite=overwrite
    )


# ── Twilio webhook ─────────────────────────────────────────────────────────────

@router.post(
    "/webhooks/twilio/status",
    status_code=200,
    include_in_schema=False,  # public webhook — keep off Swagger
    summary="Twilio status callback",
    description=(
        "Receives Twilio delivery status callbacks. "
        "Updates notification records with DELIVERED/FAILED status. "
        "This endpoint is PUBLIC — Twilio posts to it without Bearer auth. "
        "TODO: verify X-Twilio-Signature header for production."
    ),
)
async def twilio_status_callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    ErrorCode: str | None = Form(default=None),
) -> dict:
    await NotificationService(db).handle_twilio_status_callback(
        message_sid=MessageSid,
        message_status=MessageStatus,
    )
    return {"received": True}
