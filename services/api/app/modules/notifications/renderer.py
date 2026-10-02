"""
NotificationRenderer — Jinja2-based template engine for notification bodies.

Variables available in all templates:
  {{ patient_name }}        — first name (safe for personalisation)
  {{ patient_full_name }}   — full name
  {{ doctor_name }}         — e.g. "Dr. Sharma"
  {{ department }}          — department display name
  {{ hospital_name }}       — hospital display name
  {{ appointment_date }}    — e.g. "Monday, 06 October 2026"
  {{ appointment_time }}    — e.g. "10:30 AM"
  {{ appointment_ref }}     — short reference code (first 8 chars of UUID, uppercased)
  {{ cancellation_reason }} — populated for cancelled events
  {{ emergency_number }}    — hospital emergency phone
"""

from __future__ import annotations

from typing import Any

import structlog
from jinja2 import Environment, StrictUndefined, TemplateError, UndefinedError

logger = structlog.get_logger(__name__)

_jinja_env = Environment(
    undefined=StrictUndefined,   # raise on missing variables — no silent blanks
    autoescape=False,            # notification bodies are plain text / WhatsApp markdown
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(template_body: str, context: dict[str, Any]) -> str:
    """
    Render a Jinja2 template with the given context.

    Raises:
        ValueError: if a required variable is missing in the template
        ValueError: if the template has a syntax error
    """
    try:
        template = _jinja_env.from_string(template_body)
        return template.render(**context)
    except UndefinedError as exc:
        raise ValueError(f"Missing template variable: {exc}") from exc
    except TemplateError as exc:
        raise ValueError(f"Template render error: {exc}") from exc


def safe_render(template_body: str, context: dict[str, Any]) -> str:
    """
    Render with fallback: if rendering fails, return the raw body.
    Used in worker dispatch to ensure delivery even with broken templates.
    """
    try:
        return render_template(template_body, context)
    except ValueError as exc:
        logger.warning("template_render_failed", error=str(exc))
        return template_body  # send raw template as last resort
