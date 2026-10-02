"""
SearchDoctorsTool — find doctors by name, specialization, or department.
"""

from typing import Any

from app.ai.tools.base import AITool, ToolContext


class SearchDoctorsTool(AITool):
    name = "search_doctors"
    description = (
        "Search for doctors in the hospital by name, specialization, or department. "
        "Use this to help a patient find the right doctor for their complaint. "
        "Always call get_doctor_availability after finding a doctor to show real slot times."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Search term — doctor name or medical specialty (e.g., 'cardiologist', 'Dr. Sharma')",
            },
            "department_id": {
                "type": "STRING",
                "description": "Optional: UUID of department to restrict search",
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        query: str,
        department_id: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from app.modules.doctors.repository import DoctorRepository

        try:
            repo = DoctorRepository(context.db)
            dept_uuid = None
            if department_id:
                import uuid
                try:
                    dept_uuid = uuid.UUID(department_id)
                except ValueError:
                    return {"error": "Invalid department_id format"}

            items, total = await repo.list(
                context.hospital_id,
                search=query,
                department_id=dept_uuid,
                is_active=True,
                limit=6,
                offset=0,
            )

            doctors = []
            for d in items:
                fee = None
                if d.consultation_fee_paise:
                    fee = f"₹{d.consultation_fee_paise // 100}"
                doctors.append({
                    "id": str(d.id),
                    "name": d.full_name,
                    "specialization": d.specialization or "General",
                    "qualifications": d.qualifications,
                    "consultation_fee": fee,
                    "is_available": d.status == "ACTIVE",
                })

            if not doctors:
                return {
                    "found": False,
                    "total": 0,
                    "message": f"No doctors found matching '{query}'. Try a different search term.",
                }

            return {"found": True, "total": total, "doctors": doctors}

        except Exception as exc:
            return {"error": f"Doctor search failed: {exc}"}
