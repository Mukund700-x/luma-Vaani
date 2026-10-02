"""
Default notification template content.

Each hospital gets these templates seeded on creation (or via the
POST /notification-templates/seed endpoint). Hospitals can then
customise templates through the admin API.

Templates support Jinja2 syntax:
  {{ variable_name }}

All WhatsApp templates use WhatsApp markdown:
  *bold*, _italic_, `code`
"""

from __future__ import annotations
from typing import NamedTuple


class TemplateSpec(NamedTuple):
    event_type: str
    channel: str
    language: str
    subject: str | None  # None for SMS/WhatsApp
    body: str


# ── appointment.confirmed ─────────────────────────────────────────────────────

CONFIRMED_SMS_EN = TemplateSpec(
    event_type="appointment.confirmed",
    channel="SMS",
    language="en",
    subject=None,
    body=(
        "Hi {{ patient_name }}, your appointment with {{ doctor_name }} "
        "({{ department }}) at {{ hospital_name }} is CONFIRMED for "
        "{{ appointment_date }} at {{ appointment_time }}. "
        "Ref: {{ appointment_ref }}. Need help? Reply HELP."
    ),
)

CONFIRMED_WHATSAPP_EN = TemplateSpec(
    event_type="appointment.confirmed",
    channel="WHATSAPP",
    language="en",
    subject=None,
    body="""\
✅ *Appointment Confirmed!*

Hello {{ patient_name }} 👋

Here are your appointment details:

🏥 *Hospital:* {{ hospital_name }}
👨‍⚕️ *Doctor:* {{ doctor_name }}
🏢 *Department:* {{ department }}
📅 *Date:* {{ appointment_date }}
⏰ *Time:* {{ appointment_time }}
🔖 *Reference:* `{{ appointment_ref }}`

💡 Please arrive *10 minutes early* and carry any previous medical records.

Need to cancel? Reply *CANCEL* or call us.
We'll see you soon! 💙""",
)

CONFIRMED_EMAIL_EN = TemplateSpec(
    event_type="appointment.confirmed",
    channel="EMAIL",
    language="en",
    subject="✅ Appointment Confirmed — {{ hospital_name }}",
    body="""\
Hi {{ patient_name }},

Your appointment has been successfully confirmed. Here are your details:

  Doctor:     {{ doctor_name }}
  Department: {{ department }}
  Hospital:   {{ hospital_name }}
  Date:       {{ appointment_date }}
  Time:       {{ appointment_time }}
  Reference:  {{ appointment_ref }}

Please arrive 10 minutes early and bring any relevant medical records or prescriptions.

If you need to cancel or reschedule, please do so at least 2 hours before your appointment.

Thank you for choosing {{ hospital_name }}.

Warm regards,
The {{ hospital_name }} Team""",
)

# ── appointment.reminder_24h ──────────────────────────────────────────────────

REMINDER_24H_SMS_EN = TemplateSpec(
    event_type="appointment.reminder_24h",
    channel="SMS",
    language="en",
    subject=None,
    body=(
        "Reminder: You have an appointment with {{ doctor_name }} at "
        "{{ hospital_name }} TOMORROW at {{ appointment_time }}. "
        "Arrive 10 mins early. Ref: {{ appointment_ref }}."
    ),
)

REMINDER_24H_WHATSAPP_EN = TemplateSpec(
    event_type="appointment.reminder_24h",
    channel="WHATSAPP",
    language="en",
    subject=None,
    body="""\
🔔 *Appointment Reminder — Tomorrow*

Hi {{ patient_name }}! Just a friendly reminder about your appointment tomorrow.

👨‍⚕️ *{{ doctor_name }}* — {{ department }}
⏰ *{{ appointment_time }}* on {{ appointment_date }}
🏥 {{ hospital_name }}

💡 Bring any previous reports or prescriptions.
🚗 Please arrive *10 minutes early*.

Need to cancel? Do so *at least 2 hours before* the appointment.
See you tomorrow! 👋""",
)

# ── appointment.reminder_2h ───────────────────────────────────────────────────

REMINDER_2H_SMS_EN = TemplateSpec(
    event_type="appointment.reminder_2h",
    channel="SMS",
    language="en",
    subject=None,
    body=(
        "Your appointment with {{ doctor_name }} at {{ hospital_name }} "
        "is in ~2 hours at {{ appointment_time }}. Please leave now to arrive on time."
    ),
)

REMINDER_2H_WHATSAPP_EN = TemplateSpec(
    event_type="appointment.reminder_2h",
    channel="WHATSAPP",
    language="en",
    subject=None,
    body="""\
⏰ *Appointment in ~2 Hours!*

Hi {{ patient_name }}, your appointment is coming up soon.

👨‍⚕️ *{{ doctor_name }}*
🕐 *{{ appointment_time }}* today
🏥 {{ hospital_name }}

Please make your way now so you arrive on time. 🚗

If you're running late, call us at {{ emergency_number }}.""",
)

# ── appointment.cancelled ─────────────────────────────────────────────────────

CANCELLED_SMS_EN = TemplateSpec(
    event_type="appointment.cancelled",
    channel="SMS",
    language="en",
    subject=None,
    body=(
        "Hi {{ patient_name }}, your appointment with {{ doctor_name }} on "
        "{{ appointment_date }} at {{ hospital_name }} has been cancelled. "
        "To rebook, contact us or use our app. Ref: {{ appointment_ref }}."
    ),
)

CANCELLED_WHATSAPP_EN = TemplateSpec(
    event_type="appointment.cancelled",
    channel="WHATSAPP",
    language="en",
    subject=None,
    body="""\
❌ *Appointment Cancelled*

Hi {{ patient_name }},

Your appointment with *{{ doctor_name }}* ({{ department }}) on *{{ appointment_date }}* has been cancelled.

🔖 Reference: `{{ appointment_ref }}`

Would you like to rebook? We can help you find another convenient slot.
Reply *BOOK* or contact us at {{ hospital_name }}.

Sorry for any inconvenience. 💙""",
)

CANCELLED_EMAIL_EN = TemplateSpec(
    event_type="appointment.cancelled",
    channel="EMAIL",
    language="en",
    subject="❌ Appointment Cancelled — {{ hospital_name }}",
    body="""\
Hi {{ patient_name }},

Your appointment has been cancelled. Here are the details:

  Doctor:     {{ doctor_name }}
  Department: {{ department }}
  Hospital:   {{ hospital_name }}
  Date:       {{ appointment_date }}
  Reference:  {{ appointment_ref }}

If you'd like to rebook or have any questions, please contact us.

We're sorry for any inconvenience.

Regards,
The {{ hospital_name }} Team""",
)

# ── appointment.rescheduled ───────────────────────────────────────────────────

RESCHEDULED_SMS_EN = TemplateSpec(
    event_type="appointment.rescheduled",
    channel="SMS",
    language="en",
    subject=None,
    body=(
        "Hi {{ patient_name }}, your appointment with {{ doctor_name }} has been "
        "rescheduled to {{ appointment_date }} at {{ appointment_time }} at {{ hospital_name }}. "
        "New Ref: {{ appointment_ref }}."
    ),
)

RESCHEDULED_WHATSAPP_EN = TemplateSpec(
    event_type="appointment.rescheduled",
    channel="WHATSAPP",
    language="en",
    subject=None,
    body="""\
🔄 *Appointment Rescheduled*

Hi {{ patient_name }},

Your appointment has been moved to a new time.

👨‍⚕️ *{{ doctor_name }}* — {{ department }}
📅 *New Date:* {{ appointment_date }}
⏰ *New Time:* {{ appointment_time }}
🏥 {{ hospital_name }}
🔖 *New Ref:* `{{ appointment_ref }}`

All good? See you then! 💙
If you have questions, just reply here.""",
)


# ── Master default list ───────────────────────────────────────────────────────

DEFAULT_TEMPLATES: list[TemplateSpec] = [
    CONFIRMED_SMS_EN,
    CONFIRMED_WHATSAPP_EN,
    CONFIRMED_EMAIL_EN,
    REMINDER_24H_SMS_EN,
    REMINDER_24H_WHATSAPP_EN,
    REMINDER_2H_SMS_EN,
    REMINDER_2H_WHATSAPP_EN,
    CANCELLED_SMS_EN,
    CANCELLED_WHATSAPP_EN,
    CANCELLED_EMAIL_EN,
    RESCHEDULED_SMS_EN,
    RESCHEDULED_WHATSAPP_EN,
]
