"""
Notification background worker.

Polls the DB every NOTIFICATION_WORKER_INTERVAL_SECONDS for PENDING
notifications whose scheduled_at <= NOW and dispatches them.

Used for:
  - Reminder notifications (24h, 2h before appointment)
  - Retry of temporarily-failed notifications

The worker runs as an asyncio background task started in app lifespan.
It uses its own DB session (separate from request sessions).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.notifications.dispatcher import NotificationDispatcher
from app.modules.notifications.models import Notification
from app.modules.notifications.repository import NotificationRepository

logger = structlog.get_logger(__name__)


async def _process_notification(
    notif: Notification,
    db: AsyncSession,
    dispatcher: NotificationDispatcher,
) -> None:
    """Dispatch one notification and update its status in the DB."""
    repo = NotificationRepository(db)
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
        fields["status"] = "SENT"
        fields["sent_at"] = now
        logger.info(
            "worker_notification_sent",
            notification_id=str(notif.id),
            channel=notif.channel,
            event_type=notif.event_type,
        )
    else:
        fields["error_message"] = result.error_message
        next_attempt = notif.attempt_count + 1
        if next_attempt >= notif.max_attempts:
            fields["status"] = "FAILED"
            logger.warning(
                "worker_notification_failed_permanently",
                notification_id=str(notif.id),
                channel=notif.channel,
                attempts=next_attempt,
            )
        else:
            logger.info(
                "worker_notification_retry_pending",
                notification_id=str(notif.id),
                attempt=next_attempt,
                max_attempts=notif.max_attempts,
            )

    await repo.update(notif.id, fields)


async def run_notification_worker(session_factory) -> None:
    """
    Long-running background task. Runs until the event loop is cancelled.

    Args:
        session_factory: Callable that returns an async DB session context manager.
                         Typically: async_sessionmaker(engine)
    """
    if not settings.NOTIFICATIONS_ENABLED:
        logger.info("notification_worker_disabled")
        return

    dispatcher = NotificationDispatcher(settings)
    interval = settings.NOTIFICATION_WORKER_INTERVAL_SECONDS

    logger.info(
        "notification_worker_started",
        interval_seconds=interval,
        provider="auto-detect",
    )

    while True:
        try:
            async with session_factory() as db:
                repo = NotificationRepository(db)
                batch = await repo.get_pending_batch(limit=50)

                if batch:
                    logger.info("worker_processing_batch", count=len(batch))
                    for notif in batch:
                        try:
                            await _process_notification(notif, db, dispatcher)
                        except Exception as exc:
                            logger.exception(
                                "worker_notification_error",
                                notification_id=str(notif.id),
                                error=str(exc),
                            )
                    await db.commit()

        except asyncio.CancelledError:
            logger.info("notification_worker_cancelled")
            break
        except Exception as exc:
            logger.exception("worker_loop_error", error=str(exc))

        await asyncio.sleep(interval)

    logger.info("notification_worker_stopped")
