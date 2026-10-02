"""
Appointment management tools for the AI layer.
  - GetPatientAppointmentsTool: view a patient's upcoming appointments
  - CancelAppointmentTool: cancel a specific appointment
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.ai.tools.base import AITool, ToolContext


class GetPatientAppointmentsTool(AITool):
    name = "get_patient_appointments"
    description = (
        "Get the upcoming appointments for the identified patient. "
        "Requires find_patient to have been called first. "
        "Shows CONFIRMED appointments in chronological order."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "status_filter": {
                "type": "STRING",
                "description": "Optional: filter by status — CONFIRMED, CANCELLED, COMPLETED, ALL",
            },
            "include_past": {
                "type": "BOOLEAN",
                "description": "Include past appointments (default: false, only future)",
            },
        },
        "required": [],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        status_filter: str | None = None,
        include_past: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if context.patient_id is None:
            return {"error": "Patient not identified. Call find_patient first."}

        try:
            from app.core.enums import AppointmentStatus
            from app.modules.appointments.repository import AppointmentRepository
            from zoneinfo import ZoneInfo

            repo = AppointmentRepository(context.db)
            tz = ZoneInfo(context.timezone)
            now_utc = datetime.now(UTC)

            status = None
            if status_filter and status_filter.upper() != "ALL":
                try:
                    status = AppointmentStatus(status_filter.upper())
                except ValueError:
                    pass  # ignore invalid status filter

            date_from = None if include_past else now_utc

            items, total = await repo.list(
                context.hospital_id,
                patient_id=context.patient_id,
                status=status or AppointmentStatus.CONFIRMED,
                date_from=date_from,
                limit=10,
                offset=0,
            )

            if not items:
                label = "upcoming" if not include_past else ""
                return {
                    "found": False,
                    "total": 0,
                    "message": f"No {label} appointments found.",
                }

            formatted = []
            for apt in items:
                local_dt = apt.scheduled_at.astimezone(tz)
                formatted.append({
                    "appointment_id": str(apt.id),
                    "date": local_dt.strftime("%A, %d %B %Y"),
                    "time": local_dt.strftime("%I:%M %p"),
                    "doctor_id": str(apt.doctor_id),
                    "department_id": str(apt.department_id),
                    "status": apt.status,
                    "duration_minutes": apt.duration_minutes,
                })

            return {"found": True, "total": total, "appointments": formatted}

        except Exception as exc:
            return {"error": f"Could not fetch appointments: {exc}"}


class CancelAppointmentTool(AITool):
    name = "cancel_appointment"
    description = (
        "Cancel a specific appointment for the identified patient. "
        "Requires find_patient first. "
        "The appointment_id must come from get_patient_appointments. "
        "Cancellation cutoff rules (e.g., 2 hours before) are enforced automatically."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "appointment_id": {
                "type": "STRING",
                "description": "UUID of the appointment to cancel (from get_patient_appointments)",
            },
            "reason": {
                "type": "STRING",
                "description": "Reason for cancellation (optional but recommended)",
            },
        },
        "required": ["appointment_id"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        appointment_id: str,
        reason: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if context.patient_id is None:
            return {"error": "Patient not identified. Call find_patient first."}

        try:
            apt_uuid = uuid.UUID(appointment_id)
        except ValueError:
            return {"error": "Invalid appointment_id format"}

        try:
            from app.modules.appointments.repository import AppointmentRepository
            from app.modules.appointments.schemas import AppointmentCancelRequest
            from app.modules.appointments.service import AppointmentService

            # Verify this appointment belongs to the identified patient
            repo = AppointmentRepository(context.db)
            apt = await repo.get_by_id(apt_uuid, context.hospital_id)
            if not apt:
                return {"error": "Appointment not found"}
            if apt.patient_id != context.patient_id:
                return {"error": "This appointment does not belong to the identified patient"}

            class _AIActor:
                id = uuid.UUID("00000000-0000-0000-0000-000000000001")
                role = "PATIENT"
                hospital_id = context.hospital_id

            svc = AppointmentService(context.db)
            cancelled = await svc.cancel_appointment(
                apt_uuid,
                context.hospital_id,
                AppointmentCancelRequest(reason=reason),
                actor=_AIActor(),  # type: ignore[arg-type]
            )

            return {
                "success": True,
                "appointment_id": str(cancelled.id),
                "message": "Your appointment has been successfully cancelled.",
            }

        except Exception as exc:
            return {"success": False, "error": str(exc)}
