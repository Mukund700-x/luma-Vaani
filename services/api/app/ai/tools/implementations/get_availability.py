"""
GetAvailabilityTool — the primary slot-availability tool for the AI.

ARCHITECTURE NOTE (ADR-003):
  The AI MUST NEVER assume or invent appointment slots.
  It MUST call this tool to get real, live availability from the AvailabilityEngine.
  The AvailabilityEngine applies schedule rules, exceptions, and existing bookings.
  What this tool returns is the ONLY source of truth for slot availability.
"""

import uuid
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.tools.base import AITool, ToolContext


class GetAvailabilityTool(AITool):
    name = "get_doctor_availability"
    description = (
        "Get real available appointment slots for a doctor. "
        "ALWAYS call this before booking — never assume slots are available. "
        "Returns a list of bookable time slots. Each slot has a slot_key — "
        "pass slot_key exactly as returned when calling book_appointment."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "doctor_id": {
                "type": "STRING",
                "description": "UUID of the doctor (from search_doctors result)",
            },
            "date_from": {
                "type": "STRING",
                "description": "Start date in YYYY-MM-DD format. Defaults to today.",
            },
            "date_to": {
                "type": "STRING",
                "description": "End date in YYYY-MM-DD format. Defaults to 7 days from today.",
            },
        },
        "required": ["doctor_id"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        doctor_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from app.modules.appointments.repository import AppointmentRepository
        from app.modules.schedules.engine import AvailabilityEngine
        from app.modules.schedules.repository import ScheduleRepository

        try:
            doctor_uuid = uuid.UUID(doctor_id)
        except ValueError:
            return {"error": "Invalid doctor_id format"}

        try:
            tz = ZoneInfo(context.timezone)
            today = date.today()

            d_from = (
                date.fromisoformat(date_from) if date_from else today
            )
            d_to = (
                date.fromisoformat(date_to) if date_to else today + timedelta(days=6)
            )

            # Safety cap: never let AI query more than 14 days at once
            if (d_to - d_from).days > 14:
                d_to = d_from + timedelta(days=13)

            engine = AvailabilityEngine(
                schedule_repo=ScheduleRepository(context.db),
                appointment_repo=AppointmentRepository(context.db),
            )
            slots = await engine.get_available_slots(
                doctor_id=doctor_uuid,
                hospital_id=context.hospital_id,
                date_from=d_from,
                date_to=d_to,
                hospital_timezone=context.timezone,
            )

            if not slots:
                return {
                    "available": False,
                    "total_slots": 0,
                    "message": (
                        f"No available slots found between {d_from} and {d_to}. "
                        "Try a wider date range or a different doctor."
                    ),
                }

            # Format slots for LLM consumption
            formatted = []
            for s in slots[:20]:  # cap at 20 slots to avoid context overflow
                local_dt = s.scheduled_at.astimezone(tz)
                formatted.append({
                    "slot_key": s.scheduled_at.isoformat(),  # pass this back for booking
                    "date": local_dt.strftime("%A, %d %B %Y"),  # e.g. "Monday, 06 October 2026"
                    "time": local_dt.strftime("%I:%M %p"),       # e.g. "10:30 AM"
                    "duration_minutes": s.duration_minutes,
                })

            return {
                "available": True,
                "total_slots": len(slots),
                "showing": len(formatted),
                "date_range": f"{d_from} to {d_to}",
                "slots": formatted,
            }

        except Exception as exc:
            return {"error": f"Availability check failed: {exc}"}
