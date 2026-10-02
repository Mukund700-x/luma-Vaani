"""
BookAppointmentTool — create an appointment on behalf of a patient.

SAFETY REQUIREMENTS:
  1. patient_id must be in ToolContext (set by find_patient tool first)
  2. slot_key must come verbatim from get_doctor_availability output
  3. All validation goes through AppointmentService.create_appointment
     which calls AvailabilityEngine.validate_slot — AI cannot bypass this
  4. Double-booking is prevented by DB partial unique index (migration 004)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.tools.base import AITool, ToolContext


class BookAppointmentTool(AITool):
    name = "book_appointment"
    description = (
        "Book an appointment for the identified patient. "
        "REQUIREMENTS before calling: "
        "(1) Patient must be identified via find_patient. "
        "(2) slot_key must be copied exactly from get_doctor_availability output. "
        "(3) department_id must be provided. "
        "Returns confirmation details on success."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "doctor_id": {
                "type": "STRING",
                "description": "UUID of the doctor",
            },
            "department_id": {
                "type": "STRING",
                "description": "UUID of the department",
            },
            "slot_key": {
                "type": "STRING",
                "description": "Exact slot_key from get_doctor_availability (ISO datetime string)",
            },
            "chief_complaint": {
                "type": "STRING",
                "description": "Patient's reason for visit in their own words (optional)",
            },
        },
        "required": ["doctor_id", "department_id", "slot_key"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        doctor_id: str,
        department_id: str,
        slot_key: str,
        chief_complaint: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        # Guard: patient must be identified
        if context.patient_id is None:
            return {
                "success": False,
                "error": (
                    "Patient not yet identified. "
                    "Please call find_patient with the patient's phone number first."
                ),
            }

        try:
            doctor_uuid = uuid.UUID(doctor_id)
            dept_uuid = uuid.UUID(department_id)
        except ValueError:
            return {"error": "Invalid doctor_id or department_id format"}

        # Parse slot_key back to datetime
        try:
            scheduled_at = datetime.fromisoformat(slot_key)
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return {"error": f"Invalid slot_key format: '{slot_key}'. Use the exact value from get_doctor_availability."}

        try:
            from app.core.enums import AppointmentSource, AppointmentType
            from app.modules.appointments.schemas import AppointmentCreate
            from app.modules.appointments.service import AppointmentService
            from app.modules.auth.models import User

            # Build a synthetic actor representing the AI system
            # The actual DB actor is the system user — audit logged with conversation_id
            class _AIActor:
                id = uuid.UUID("00000000-0000-0000-0000-000000000001")  # system sentinel
                role = "HOSPITAL_ADMIN"  # AI acts with admin-level booking rights
                hospital_id = context.hospital_id

            payload = AppointmentCreate(
                patient_id=context.patient_id,
                doctor_id=doctor_uuid,
                department_id=dept_uuid,
                scheduled_at=scheduled_at,
                appointment_type=AppointmentType.OPD,
                source=AppointmentSource.AI_CHAT,
                chief_complaint=chief_complaint,
                conversation_id=context.conversation_id,
            )

            svc = AppointmentService(context.db)
            apt = await svc.create_appointment(
                context.hospital_id, payload, actor=_AIActor()  # type: ignore[arg-type]
            )

            # Format confirmation for the patient
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(context.timezone)
            local_dt = apt.scheduled_at.astimezone(tz)

            return {
                "success": True,
                "appointment_id": str(apt.id),
                "confirmation": {
                    "date": local_dt.strftime("%A, %d %B %Y"),
                    "time": local_dt.strftime("%I:%M %p"),
                    "duration": f"{apt.duration_minutes} minutes",
                    "status": apt.status,
                },
                "message": (
                    f"Appointment confirmed! "
                    f"Your appointment is on {local_dt.strftime('%A, %d %B at %I:%M %p')}."
                ),
            }

        except Exception as exc:
            # Surface meaningful errors (slot taken, doctor inactive, etc.)
            return {"success": False, "error": str(exc)}
