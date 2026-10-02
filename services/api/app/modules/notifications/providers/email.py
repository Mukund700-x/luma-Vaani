"""
SMTPEmailProvider — async email delivery via aiosmtplib.

Sends HTML and plain-text multipart email.
Requires: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL

PHI NOTE: recipient email addresses are NEVER logged.
"""

import structlog

from app.modules.notifications.providers.base import (
    DeliveryResult,
    NotificationProvider,
    ProviderName,
)

logger = structlog.get_logger(__name__)

try:
    import aiosmtplib
    _SMTP_AVAILABLE = True
except ImportError:
    _SMTP_AVAILABLE = False


class SMTPEmailProvider(NotificationProvider):
    """
    Async SMTP email provider using aiosmtplib.
    Supports TLS/STARTTLS and plain auth.
    """

    provider_name = ProviderName.SMTP

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        from_name: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._from_name = from_name
        self._use_tls = use_tls

    @property
    def is_available(self) -> bool:
        return _SMTP_AVAILABLE and bool(self._host and self._from_email)

    async def send(
        self,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> DeliveryResult:
        if not _SMTP_AVAILABLE:
            return DeliveryResult(
                success=False,
                provider=ProviderName.SMTP,
                error_message="aiosmtplib not installed (pip install aiosmtplib)",
            )

        if not self.is_available:
            return DeliveryResult(
                success=False,
                provider=ProviderName.SMTP,
                error_message="SMTP provider is not configured",
            )

        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            import uuid

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject or "Notification from Luma Vaani"
            msg["From"] = f"{self._from_name} <{self._from_email}>"
            msg["To"] = recipient
            msg["Message-ID"] = f"<{uuid.uuid4()}@lumahealth.io>"

            # Plain text version (always included)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # HTML version: wrap body in a minimal brand-styled template
            html_body = _render_html_email(
                body=body,
                subject=subject or "Notification",
                from_name=self._from_name,
            )
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            smtp_kwargs = {
                "hostname": self._host,
                "port": self._port,
                "use_tls": False,
                "start_tls": self._use_tls,
            }
            if self._username and self._password:
                smtp_kwargs["username"] = self._username
                smtp_kwargs["password"] = self._password

            await aiosmtplib.send(msg, **smtp_kwargs)

            logger.info(
                "email_sent",
                subject=subject,
                # No recipient logged — PHI
            )
            return DeliveryResult(
                success=True,
                provider=ProviderName.SMTP,
                provider_message_id=msg["Message-ID"],
                provider_status="sent",
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error("email_send_failed", error=error_msg)
            return DeliveryResult(
                success=False,
                provider=ProviderName.SMTP,
                error_message=error_msg[:500],
            )


def _render_html_email(body: str, subject: str, from_name: str) -> str:
    """
    Wraps plain-text body in a minimal, brand-grade HTML email template.
    Converts newlines to <br> tags.
    """
    html_body = body.replace("\n", "<br>").replace("**", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#5B4CF5 0%,#2F9CF1 100%);padding:32px 40px;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
              💙 {from_name}
            </h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
              Your AI-powered hospital front desk
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0;color:#1a1a2e;font-size:15px;line-height:1.7;">{html_body}</p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px 32px;border-top:1px solid #f0f0f0;">
            <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.6;">
              This is an automated message from {from_name}. Please do not reply to this email.<br>
              If you need assistance, contact your hospital directly.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
