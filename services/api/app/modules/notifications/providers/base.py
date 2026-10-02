"""
NotificationProvider abstract base and DeliveryResult.

All concrete providers (Twilio SMS, WhatsApp, SMTP) implement this interface.
The dispatcher selects the correct provider at runtime based on channel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ProviderName(str, Enum):
    TWILIO_SMS = "twilio_sms"
    TWILIO_WHATSAPP = "twilio_whatsapp"
    SMTP = "smtp"
    STUB = "stub"


@dataclass(frozen=True)
class DeliveryResult:
    """
    Immutable result of a single notification delivery attempt.
    provider_message_id is the external SID (Twilio) or message-id (email).
    """

    success: bool
    provider: ProviderName
    provider_message_id: str | None = None
    provider_status: str | None = None
    error_message: str | None = None
    attempted_at: datetime = field(default_factory=datetime.utcnow)


class NotificationProvider(ABC):
    """
    Abstract base class for all notification delivery providers.

    Subclasses MUST:
    - Return DeliveryResult(success=False, error_message=...) on errors (never raise)
    - Never log recipient phone numbers or email addresses (PHI)
    - Be instantiated fresh per request (stateless preferred)
    """

    provider_name: ProviderName

    @abstractmethod
    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        """
        Deliver a notification.

        Args:
            recipient: Phone number (+E.164 format) or email address
            body: Rendered message body (plain text or WhatsApp markdown)
            subject: Subject line (email only, ignored by SMS/WhatsApp)

        Returns:
            DeliveryResult — always returns, never raises
        """
        ...

    @property
    def is_available(self) -> bool:
        """Returns True if this provider is configured and ready to send."""
        return True
