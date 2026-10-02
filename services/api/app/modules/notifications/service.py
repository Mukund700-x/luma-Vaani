"""
Notification service — orchestrates template lookup, rendering, queuing, and dispatch.

PUBLIC API:
  queue_for_appointment()  — the primary entry point; called by AppointmentService
  seed_default_templates() — seeds hospital with all default templates
  retry_notification()     — re-queue a FAILED notification
  list_notifications()     — paginated history for admin
  list_templates()         — template CRUD for admin
  upsert_template()        — create or update a template
  handle_twilio_webhook()  — update delivery status from Twilio callbacks

DELIVERY MODEL:
  Immediate (confirmations, cancellations): queued then dispatched inline
  Scheduled (reminders): queued with future scheduled_at; worker dispatches later

PHI SAFETY:
  recipient and rendered body are stored in DB but NEVER written to audit logs
  All audit logs reference only notification_id, event_type, channel, status
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.config import settings
from app.core.enums import AuditActorType, NotificationStatus, UserRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.notifications.defaults import DEFAULT_TEMPLATES
from app.modules.notifications.dispatcher import NotificationDispatcher
from app.modules.notifications.models import Notification, NotificationTemplate
from app.modules.notifications.renderer import safe_render
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    NotificationRetryResponse,
    NotificationSummary,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
)

logger = structlog.get_logger(__name__)

_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}
_STAFF_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.RECEPTIONIST}

# Which channels to notify per hospital (configurable via hospital.config)
_DEFAULT_CHANNELS = ["SMS", "WHATSAPP"]

# Reminder offsets
_REMINDER_OFFSETS: dict[str, timedelta] = {
    "appointment.reminder_24h": timedelta(hours=24),
    "appointment.reminder_2h": timedelta(hours=2),
}


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = NotificationRepository(db)
        self._audit = AuditService(db)

    # ── Core: queue notifications for an appointment event ────────────────────

    async def queue_for_appointment(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        event_type: str,
        dispatch_immediately: bool = True,
    ) -> list[Notification]:
        """
        Queue notification records for an appointment event on all configured channels.
        If dispatch_immediately=True, also attempts delivery inline (fire-and-forget resilient).
        Always includes reminder scheduling for appointment.confirmed events.
        """
        if not settings.NOTIFICATIONS_ENABLED:
            logger.debug("notifications_disabled", event_type=event_type)
            return []

        try:
            context = await self._build_appointment_context(appointment_id, hospital_id)
        except Exception as exc:
            logger.warning("notification_context_build_failed", error=str(exc), appointment_id=str(appointment_id))
            return []

        if context is None:
            return []

        patient = context["patient"]
        hospital_config = context["hospital_config"]
        channels = hospital_config.get("notification_channels", _DEFAULT_CHANNELS)
        language = context.get("language", "en")

        queued: list[Notification] = []

        for channel in channels:
            recipient = self._get_recipient(patient, channel)
            if not recipient:
                continue

            tmpl = await self._repo.get_template(hospital_id, event_type, channel, language)
            if not tmpl:
                logger.debug("no_template_found", event_type=event_type, channel=channel)
                continue

            rendered_body = safe_render(tmpl.body, context["vars"])
            rendered_subject = safe_render(tmpl.subject, context["vars"]) if tmpl.subject else None

            notif = await self._repo.create(
                hospital_id,
                patient_id=patient.id,
                appointment_id=appointment_id,
                channel=channel,
                status=NotificationStatus.PENDING.value,
                event_type=event_type,
                recipient=recipient,
                subject=rendered_subject,
                body=rendered_body,
                scheduled_at=datetime.now(UTC),
            )
            queued.append(notif)

            if dispatch_immediately:
                await self._dispatch_and_update(notif)

        # Queue reminder notifications for newly confirmed appointments
        if event_type == "appointment.confirmed":
            await self._queue_reminders(
                appointment_id=appointment_id,
                hospital_id=hospital_id,
                context=context,
                channels=channels,
                language=language,
            )

        logger.info(
            "notifications_queued",
            event_type=event_type,
            appointment_id=str(appointment_id),
            count=len(queued),
        )
        return queued

    async def _queue_reminders(
        self,
        appointment_id: uuid.UUID,
        hospital_id: uuid.UUID,
        context: dict,
        channels: list[str],
        language: str,
    ) -> None:
        """Queue 24h and 2h reminder notifications for a confirmed appointment."""
        scheduled_at = context["vars"].get("_scheduled_at_utc")
        if not scheduled_at:
            return

        patient = context["patient"]

        for event_type, offset in _REMINDER_OFFSETS.items():
            send_at = scheduled_at - offset
            if send_at <= datetime.now(UTC):
                continue  # appointment too soon for this reminder

            for channel in channels:
                recipient = self._get_recipient(patient, channel)
                if not recipient:
                    continue

                tmpl = await self._repo.get_template(hospital_id, event_type, channel, language)
                if not tmpl:
                    continue

                rendered_body = safe_render(tmpl.body, context["vars"])
                rendered_subject = safe_render(tmpl.subject, context["vars"]) if tmpl.subject else None

                await self._repo.create(
                    hospital_id,
                    patient_id=patient.id,
                    appointment_id=appointment_id,
                    channel=channel,
                    status=NotificationStatus.PENDING.value,
                    event_type=event_type,
                    recipient=recipient,
                    subject=rendered_subject,
                    body=rendered_body,
                    scheduled_at=send_at,
                )

    async def _dispatch_and_update(self, notif: Notification) -> None:
        """Attempt delivery and update the notification record with the result."""
        dispatcher = NotificationDispatcher(settings)
        result = await dispatcher.dispatch(
            channel=notif.channel,
            recipient=notif.recipient,
            body=notif.body,
            subject=notif.subject,
        )

        now = datetime.now(UTC)
        fields: dict[str, Any] = {
            "attempt_count": notif.attempt_count + 1,
            "provider": result.provider.value,
            "provider_message_id": result.provider_message_id,
            "provider_status": result.provider_status,
        }
        if result.success:
            fields["status"] = NotificationStatus.SENT.value
            fields["sent_at"] = now
        else:
            fields["error_message"] = result.error_message
            if (notif.attempt_count + 1) >= notif.max_attempts:
                fields["status"] = NotificationStatus.FAILED.value
            # else stays PENDING for worker retry

        await self._repo.update(notif.id, fields)

    # ── Context builder ───────────────────────────────────────────────────────

    async def _build_appointment_context(
        self, appointment_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> dict | None:
        from zoneinfo import ZoneInfo
        from sqlalchemy import select
        from app.modules.appointments.models import Appointment
        from app.modules.doctors.models import Doctor
        from app.modules.patients.models import Patient
        from app.modules.departments.models import Department
        from app.modules.hospitals.models import Hospital

        result = await self._db.execute(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.hospital_id == hospital_id,
            )
        )
        apt = result.scalar_one_or_none()
        if not apt:
            return None

        patient = await self._db.get(Patient, apt.patient_id)
        doctor = await self._db.get(Doctor, apt.doctor_id)
        department = await self._db.get(Department, apt.department_id)
        hospital = await self._db.get(Hospital, hospital_id)

        if not (patient and doctor and department and hospital):
            return None

        config: dict = hospital.config or {}
        tz = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
        local_dt = apt.scheduled_at.astimezone(tz)
        doctor_name = doctor.full_name
        if not doctor_name.startswith("Dr."):
            doctor_name = f"Dr. {doctor_name}"

        template_vars = {
            "patient_name": patient.full_name.split()[0],
            "patient_full_name": patient.full_name,
            "doctor_name": doctor_name,
            "department": department.name,
            "hospital_name": hospital.name,
            "appointment_date": local_dt.strftime("%A, %d %B %Y"),
            "appointment_time": local_dt.strftime("%I:%M %p"),
            "appointment_ref": str(apt.id)[:8].upper(),
            "cancellation_reason": apt.cancellation_reason or "",
            "emergency_number": config.get("emergency_phone", "112"),
            "_scheduled_at_utc": apt.scheduled_at,  # internal — not in templates
        }

        return {
            "patient": patient,
            "hospital_config": config,
            "language": config.get("default_language", "en"),
            "vars": template_vars,
        }

    @staticmethod
    def _get_recipient(patient, channel: str) -> str | None:
        channel = channel.upper()
        if channel in ("SMS", "WHATSAPP"):
            return patient.phone or None
        elif channel == "EMAIL":
            return patient.email or None
        return None

    # ── Admin: retry ──────────────────────────────────────────────────────────

    async def retry_notification(
        self,
        notification_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> NotificationRetryResponse:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")

        notif = await self._repo.get_by_id(notification_id, hospital_id)
        if not notif:
            raise NotFoundException("Notification", str(notification_id))

        if notif.status not in ("FAILED", "PENDING"):
            return NotificationRetryResponse(
                notification_id=notification_id,
                queued=False,
                message=f"Cannot retry a notification with status '{notif.status}'",
            )

        await self._repo.update(notification_id, {
            "status": NotificationStatus.PENDING.value,
            "max_attempts": notif.max_attempts + 1,  # grant one extra attempt
        })
        await self._dispatch_and_update(notif)

        return NotificationRetryResponse(
            notification_id=notification_id,
            queued=True,
            message="Retry dispatched",
        )

    # ── Admin: notifications list ─────────────────────────────────────────────

    async def list_notifications(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        *,
        params: PageParams,
        patient_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        status: str | None = None,
        channel: str | None = None,
    ) -> Page[NotificationSummary]:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")

        items, total = await self._repo.list(
            hospital_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            status=status,
            channel=channel,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [NotificationSummary.from_orm_masked(n) for n in items],
            total, params,
        )

    # ── Admin: templates ──────────────────────────────────────────────────────

    async def list_templates(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        event_type: str | None = None,
        channel: str | None = None,
    ) -> list[NotificationTemplateResponse]:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")
        templates = await self._repo.list_templates(hospital_id, event_type, channel)
        return [NotificationTemplateResponse.model_validate(t) for t in templates]

    async def upsert_template(
        self,
        hospital_id: uuid.UUID,
        payload: NotificationTemplateCreate,
        actor: User,
    ) -> NotificationTemplateResponse:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")

        exists = await self._repo.template_exists(
            hospital_id, payload.event_type, payload.channel, payload.language
        )
        if exists:
            # Update existing
            templates = await self._repo.list_templates(
                hospital_id, event_type=payload.event_type, channel=payload.channel
            )
            matching = next(
                (t for t in templates if t.language == payload.language), None
            )
            if matching:
                updated = await self._repo.update_template(
                    matching.id, hospital_id,
                    {"subject": payload.subject, "body": payload.body, "is_active": True},
                )
                return NotificationTemplateResponse.model_validate(updated)

        created = await self._repo.create_template(
            hospital_id,
            event_type=payload.event_type,
            channel=payload.channel.upper(),
            language=payload.language,
            subject=payload.subject,
            body=payload.body,
            is_active=True,
            created_by=actor.id,
        )
        return NotificationTemplateResponse.model_validate(created)

    async def delete_template(
        self,
        template_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")
        deleted = await self._repo.delete_template(template_id, hospital_id)
        if not deleted:
            raise NotFoundException("NotificationTemplate", str(template_id))

    async def seed_default_templates(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        overwrite: bool = False,
    ) -> dict[str, int]:
        """Seed all DEFAULT_TEMPLATES for a hospital. Returns counts."""
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")

        created = 0
        skipped = 0
        for spec in DEFAULT_TEMPLATES:
            exists = await self._repo.template_exists(
                hospital_id, spec.event_type, spec.channel, spec.language
            )
            if exists and not overwrite:
                skipped += 1
                continue
            if exists and overwrite:
                templates = await self._repo.list_templates(hospital_id, spec.event_type, spec.channel)
                matching = next((t for t in templates if t.language == spec.language), None)
                if matching:
                    await self._repo.update_template(matching.id, hospital_id, {
                        "subject": spec.subject, "body": spec.body, "is_active": True
                    })
                    created += 1
                    continue
            await self._repo.create_template(
                hospital_id,
                event_type=spec.event_type,
                channel=spec.channel,
                language=spec.language,
                subject=spec.subject,
                body=spec.body,
                is_active=True,
                created_by=actor.id,
            )
            created += 1

        logger.info("templates_seeded", hospital_id=str(hospital_id), created=created, skipped=skipped)
        return {"created": created, "skipped": skipped}

    # ── Twilio webhook ────────────────────────────────────────────────────────

    async def handle_twilio_status_callback(
        self,
        message_sid: str,
        message_status: str,
    ) -> None:
        """
        Update notification delivery status from Twilio's status webhook.
        Called by the webhook endpoint — no auth (verified by request signature).
        """
        notif = await self._repo.get_by_provider_message_id(message_sid)
        if not notif:
            logger.warning("twilio_webhook_unknown_sid", sid=message_sid)
            return

        fields: dict[str, Any] = {"provider_status": message_status}
        status_upper = message_status.upper()

        if status_upper == "DELIVERED":
            fields["status"] = NotificationStatus.DELIVERED.value
            fields["delivered_at"] = datetime.now(UTC)
        elif status_upper in ("FAILED", "UNDELIVERED"):
            fields["status"] = NotificationStatus.FAILED.value

        await self._repo.update(notif.id, fields)
        logger.info("twilio_status_updated", sid=message_sid, status=message_status)
