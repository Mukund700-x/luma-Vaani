"""
NotificationDispatcher — selects the correct provider and delivers a notification.

Reads provider credentials from settings at dispatch time.
Implements exponential-backoff retry tracking (state stored in DB by caller).
"""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.modules.notifications.providers.base import DeliveryResult, ProviderName
from app.modules.notifications.providers.email import SMTPEmailProvider
from app.modules.notifications.providers.sms import TwilioSMSProvider
from app.modules.notifications.providers.stub import StubProvider
from app.modules.notifications.providers.whatsapp import TwilioWhatsAppProvider

logger = structlog.get_logger(__name__)


class NotificationDispatcher:
    """
    Resolves the correct NotificationProvider for a given channel
    and delegates delivery to it.

    Provider selection priority:
      SMS       → TwilioSMS if configured, else Stub
      WHATSAPP  → TwilioWhatsApp if configured, else Stub
      EMAIL     → SMTP if configured, else Stub
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _sms_provider(self):
        if (
            self._settings.TWILIO_ACCOUNT_SID
            and self._settings.TWILIO_AUTH_TOKEN
            and self._settings.TWILIO_SMS_FROM
        ):
            return TwilioSMSProvider(
                account_sid=self._settings.TWILIO_ACCOUNT_SID,
                auth_token=self._settings.TWILIO_AUTH_TOKEN,
                from_number=self._settings.TWILIO_SMS_FROM,
            )
        logger.warning("twilio_sms_not_configured", fallback="stub")
        return StubProvider()

    def _whatsapp_provider(self):
        if (
            self._settings.TWILIO_ACCOUNT_SID
            and self._settings.TWILIO_AUTH_TOKEN
            and self._settings.TWILIO_WHATSAPP_FROM
        ):
            return TwilioWhatsAppProvider(
                account_sid=self._settings.TWILIO_ACCOUNT_SID,
                auth_token=self._settings.TWILIO_AUTH_TOKEN,
                from_number=self._settings.TWILIO_WHATSAPP_FROM,
            )
        logger.warning("twilio_whatsapp_not_configured", fallback="stub")
        return StubProvider()

    def _email_provider(self):
        if self._settings.SMTP_HOST and self._settings.SMTP_FROM_EMAIL:
            return SMTPEmailProvider(
                host=self._settings.SMTP_HOST,
                port=self._settings.SMTP_PORT,
                username=self._settings.SMTP_USER,
                password=self._settings.SMTP_PASSWORD,
                from_email=self._settings.SMTP_FROM_EMAIL,
                from_name=self._settings.SMTP_FROM_NAME,
                use_tls=self._settings.SMTP_USE_TLS,
            )
        logger.warning("smtp_not_configured", fallback="stub")
        return StubProvider()

    def get_provider(self, channel: str):
        """Select provider for the given channel name."""
        channel_upper = channel.upper()
        if channel_upper == "SMS":
            return self._sms_provider()
        elif channel_upper == "WHATSAPP":
            return self._whatsapp_provider()
        elif channel_upper == "EMAIL":
            return self._email_provider()
        else:
            logger.error("unknown_notification_channel", channel=channel)
            return StubProvider()

    async def dispatch(
        self,
        channel: str,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        """
        Dispatch a rendered notification to the correct provider.
        Never raises — returns DeliveryResult(success=False) on any failure.
        """
        provider = self.get_provider(channel)
        try:
            result = await provider.send(
                recipient=recipient,
                body=body,
                subject=subject,
            )
            logger.info(
                "notification_dispatched",
                channel=channel,
                provider=result.provider.value,
                success=result.success,
            )
            return result
        except Exception as exc:
            logger.exception("dispatcher_error", channel=channel, error=str(exc))
            return DeliveryResult(
                success=False,
                provider=ProviderName.STUB,
                error_message=f"Dispatcher error: {exc}",
            )
