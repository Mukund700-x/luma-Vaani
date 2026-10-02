"""
TwilioSMSProvider — SMS delivery via Twilio Programmable SMS.

Requires:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_FROM

PHI NOTE: recipient phone numbers are NEVER logged.
"""

import asyncio

import structlog

from app.modules.notifications.providers.base import (
    DeliveryResult,
    NotificationProvider,
    ProviderName,
)

logger = structlog.get_logger(__name__)

try:
    from twilio.rest import Client as _TwilioClient
    from twilio.base.exceptions import TwilioRestException
    _TWILIO_AVAILABLE = True
except ImportError:
    _TWILIO_AVAILABLE = False


class TwilioSMSProvider(NotificationProvider):
    """Twilio SMS provider. Uses asyncio.to_thread for the sync Twilio client."""

    provider_name = ProviderName.TWILIO_SMS

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._client = None

    @property
    def is_available(self) -> bool:
        return _TWILIO_AVAILABLE and bool(
            self._account_sid and self._auth_token and self._from_number
        )

    def _get_client(self):
        if self._client is None:
            self._client = _TwilioClient(self._account_sid, self._auth_token)
        return self._client

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        if not _TWILIO_AVAILABLE:
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_SMS,
                error_message="Twilio package not installed (pip install twilio)",
            )

        if not self.is_available:
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_SMS,
                error_message="Twilio SMS provider is not configured",
            )

        try:
            client = self._get_client()
            message = await asyncio.to_thread(
                client.messages.create,
                body=body,
                from_=self._from_number,
                to=recipient,
            )
            logger.info(
                "sms_sent",
                sid=message.sid,
                status=message.status,
                # No recipient logged — PHI
            )
            return DeliveryResult(
                success=True,
                provider=ProviderName.TWILIO_SMS,
                provider_message_id=message.sid,
                provider_status=message.status,
            )
        except Exception as exc:  # includes TwilioRestException
            error_msg = str(exc)
            logger.error("sms_send_failed", error=error_msg)
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_SMS,
                error_message=error_msg[:500],
            )
