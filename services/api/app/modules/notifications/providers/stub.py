"""
StubProvider — silent no-op provider for development and testing.

Logs the notification intent without making any external API calls.
Automatically activated when real providers are not configured.
"""

import structlog
from app.modules.notifications.providers.base import (
    DeliveryResult,
    NotificationProvider,
    ProviderName,
)

logger = structlog.get_logger(__name__)


class StubProvider(NotificationProvider):
    """
    Development/testing provider. Always returns success without sending anything.
    Set NOTIFICATIONS_ENABLED=false to use this automatically.
    """

    provider_name = ProviderName.STUB

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        # Mask recipient for safe logging
        masked = _mask(recipient)
        logger.info(
            "stub_notification_sent",
            recipient_masked=masked,
            subject=subject,
            body_length=len(body),
        )
        return DeliveryResult(
            success=True,
            provider=ProviderName.STUB,
            provider_message_id=f"stub-{id(body):x}",
            provider_status="stub_delivered",
        )


def _mask(value: str) -> str:
    """Mask phone/email for safe log output."""
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:2]}***@{domain}"
    if len(value) > 6:
        return value[:4] + "****" + value[-2:]
    return "****"
