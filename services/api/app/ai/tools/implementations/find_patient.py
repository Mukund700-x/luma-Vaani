"""
FindPatientTool — identify a patient by phone number for conversation context.

SECURITY NOTE:
  This tool does NOT return full PHI to the LLM.
  On success, it stores the patient_id in ToolContext (server-side)
  and returns only a greeting name to the LLM.
  The LLM never sees phone number, DoB, blood group, or any sensitive PHI.
"""

from typing import Any

from app.ai.tools.base import AITool, ToolContext


class FindPatientTool(AITool):
    name = "find_patient"
    description = (
        "Identify a patient by their registered phone number. "
        "Call this before booking an appointment when you don't know who you are speaking with. "
        "On success, the patient is identified in the session — do not ask for phone again."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "phone": {
                "type": "STRING",
                "description": "Patient's registered mobile phone number (with country code if possible)",
            }
        },
        "required": ["phone"],
    }

    async def execute(self, context: ToolContext, *, phone: str, **_: Any) -> dict[str, Any]:
        from sqlalchemy import and_, select

        from app.modules.patients.models import Patient

        try:
            result = await context.db.execute(
                select(Patient).where(
                    and_(
                        Patient.hospital_id == context.hospital_id,
                        Patient.phone == phone,
                        Patient.is_active == True,  # noqa: E712
                    )
                ).limit(1)
            )
            patient = result.scalar_one_or_none()

            if not patient:
                return {
                    "found": False,
                    "message": (
                        "No registered patient found with this phone number. "
                        "Would you like to register as a new patient?"
                    ),
                }

            # Store patient_id in context — NOT returned to LLM
            context.set_patient(patient.id)

            # Return only first name — minimal safe PHI for personalisation
            first_name = patient.full_name.split()[0]
            return {
                "found": True,
                "greeting_name": first_name,
                "message": f"Patient identified. Welcome back, {first_name}!",
                "has_mrn": patient.mrn is not None,
            }

        except Exception as exc:
            return {"error": f"Could not look up patient: {exc}"}
