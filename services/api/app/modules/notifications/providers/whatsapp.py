"""
TwilioWhatsAppProvider — WhatsApp Business delivery via Twilio.

Twilio WhatsApp uses the same REST API as SMS but with:
  - from: "whatsapp:+<number>"
  - to:   "whatsapp:+<number>"

Supports WhatsApp markdown formatting:
  *bold*, _italic_, ~strikethrough~, `code`

Requires:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
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
    _TWILIO_AVAILABLE = True
except ImportError:
    _TWILIO_AVAILABLE = False

_WA_PREFIX = "whatsapp:"


class TwilioWhatsAppProvider(NotificationProvider):
    """
    WhatsApp Business provider via Twilio.
    Messages support rich WhatsApp markdown formatting.
    """

    provider_name = ProviderName.TWILIO_WHATSAPP

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        # Ensure whatsapp: prefix on sender
        self._from_number = (
            from_number if from_number.startswith(_WA_PREFIX)
            else f"{_WA_PREFIX}{from_number}"
        )
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

    @staticmethod
    def _wa_recipient(phone: str) -> str:
        """Ensure phone number has the whatsapp: prefix."""
        if phone.startswith(_WA_PREFIX):
            return phone
        return f"{_WA_PREFIX}{phone}"

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        if not _TWILIO_AVAILABLE:
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_WHATSAPP,
                error_message="Twilio package not installed (pip install twilio)",
            )

        if not self.is_available:
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_WHATSAPP,
                error_message="Twilio WhatsApp provider is not configured",
            )

        try:
            client = self._get_client()
            wa_to = self._wa_recipient(recipient)
            message = await asyncio.to_thread(
                client.messages.create,
                body=body,
                from_=self._from_number,
                to=wa_to,
            )
            logger.info(
                "whatsapp_sent",
                sid=message.sid,
                status=message.status,
                # No recipient logged — PHI
            )
            return DeliveryResult(
                success=True,
                provider=ProviderName.TWILIO_WHATSAPP,
                provider_message_id=message.sid,
                provider_status=message.status,
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error("whatsapp_send_failed", error=error_msg)
            return DeliveryResult(
                success=False,
                provider=ProviderName.TWILIO_WHATSAPP,
                error_message=error_msg[:500],
            )
