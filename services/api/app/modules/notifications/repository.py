"""
Notification repository — tenant-scoped data access.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification, NotificationTemplate


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Templates ──────────────────────────────────────────────────────────────

    async def get_template(
        self,
        hospital_id: uuid.UUID,
        event_type: str,
        channel: str,
        language: str = "en",
    ) -> NotificationTemplate | None:
        """
        Fetch the active template for (hospital, event, channel, language).
        Falls back to "en" if the requested language isn't configured.
        """
        q = select(NotificationTemplate).where(
            and_(
                NotificationTemplate.hospital_id == hospital_id,
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.channel == channel.upper(),
                NotificationTemplate.language == language,
                NotificationTemplate.is_active == True,  # noqa: E712
            )
        )
        result = await self._db.execute(q)
        tmpl = result.scalar_one_or_none()
        if tmpl or language == "en":
            return tmpl
        # Language fallback: try English
        return await self.get_template(hospital_id, event_type, channel, "en")

    async def list_templates(
        self,
        hospital_id: uuid.UUID,
        event_type: str | None = None,
        channel: str | None = None,
    ) -> list[NotificationTemplate]:
        q = select(NotificationTemplate).where(
            NotificationTemplate.hospital_id == hospital_id
        )
        if event_type:
            q = q.where(NotificationTemplate.event_type == event_type)
        if channel:
            q = q.where(NotificationTemplate.channel == channel.upper())
        q = q.order_by(NotificationTemplate.event_type, NotificationTemplate.channel)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def create_template(self, hospital_id: uuid.UUID, **fields: Any) -> NotificationTemplate:
        tmpl = NotificationTemplate(hospital_id=hospital_id, **fields)
        self._db.add(tmpl)
        await self._db.flush()
        await self._db.refresh(tmpl)
        return tmpl

    async def update_template(
        self,
        template_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> NotificationTemplate | None:
        await self._db.execute(
            update(NotificationTemplate)
            .where(
                and_(
                    NotificationTemplate.id == template_id,
                    NotificationTemplate.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        result = await self._db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def delete_template(self, template_id: uuid.UUID, hospital_id: uuid.UUID) -> bool:
        tmpl = await self._db.get(NotificationTemplate, template_id)
        if not tmpl or tmpl.hospital_id != hospital_id:
            return False
        await self._db.delete(tmpl)
        return True

    async def template_exists(
        self,
        hospital_id: uuid.UUID,
        event_type: str,
        channel: str,
        language: str,
    ) -> bool:
        result = await self._db.execute(
            select(func.count()).where(
                and_(
                    NotificationTemplate.hospital_id == hospital_id,
                    NotificationTemplate.event_type == event_type,
                    NotificationTemplate.channel == channel.upper(),
                    NotificationTemplate.language == language,
                )
            )
        )
        return (result.scalar_one() or 0) > 0

    # ── Notifications ──────────────────────────────────────────────────────────

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> Notification:
        notif = Notification(hospital_id=hospital_id, **fields)
        self._db.add(notif)
        await self._db.flush()
        await self._db.refresh(notif)
        return notif

    async def get_by_id(
        self, notification_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        status: str | None = None,
        channel: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        base_q = select(Notification).where(Notification.hospital_id == hospital_id)
        if patient_id:
            base_q = base_q.where(Notification.patient_id == patient_id)
        if appointment_id:
            base_q = base_q.where(Notification.appointment_id == appointment_id)
        if status:
            base_q = base_q.where(Notification.status == status.upper())
        if channel:
            base_q = base_q.where(Notification.channel == channel.upper())

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()
        items_q = (
            base_q.order_by(Notification.created_at.desc())
            .limit(limit).offset(offset)
        )
        items = list((await self._db.execute(items_q)).scalars().all())
        return items, total

    async def update(
        self,
        notification_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> None:
        await self._db.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(**fields)
        )

    # ── Worker queries ─────────────────────────────────────────────────────────

    async def get_pending_batch(
        self,
        limit: int = 50,
    ) -> list[Notification]:
        """
        Fetch PENDING notifications due for delivery.
        Used by the background worker.
        """
        now = datetime.now(UTC)
        result = await self._db.execute(
            select(Notification)
            .where(
                and_(
                    Notification.status == "PENDING",
                    Notification.scheduled_at <= now,
                    Notification.attempt_count < Notification.max_attempts,
                )
            )
            .order_by(Notification.scheduled_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_provider_message_id(
        self, provider_message_id: str
    ) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(
                Notification.provider_message_id == provider_message_id
            )
        )
        return result.scalar_one_or_none()
