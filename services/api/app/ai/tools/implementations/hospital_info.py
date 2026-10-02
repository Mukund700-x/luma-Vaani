"""
GetHospitalInfoTool — retrieve static hospital information for the AI.
Covers: departments list, hospital hours, contact details, emergency info.
"""

from typing import Any

from app.ai.tools.base import AITool, ToolContext


class GetHospitalInfoTool(AITool):
    name = "get_hospital_info"
    description = (
        "Get hospital information: departments, operating hours, contact details, or emergency info. "
        "Use this to answer general questions about the hospital. "
        "Do not make up information — always call this tool for hospital facts."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "info_type": {
                "type": "STRING",
                "description": (
                    "Type of information requested: "
                    "DEPARTMENTS (list all departments), "
                    "HOURS (operating hours), "
                    "CONTACT (phone, email, address), "
                    "EMERGENCY (emergency contact and protocol)"
                ),
            }
        },
        "required": ["info_type"],
    }

    async def execute(
        self,
        context: ToolContext,
        *,
        info_type: str,
        **_: Any,
    ) -> dict[str, Any]:
        try:
            info_type = info_type.upper().strip()

            if info_type == "DEPARTMENTS":
                return await self._get_departments(context)
            elif info_type == "HOURS":
                return self._get_hours(context)
            elif info_type == "CONTACT":
                return self._get_contact(context)
            elif info_type == "EMERGENCY":
                return self._get_emergency(context)
            else:
                return {
                    "error": (
                        f"Unknown info_type '{info_type}'. "
                        "Valid values: DEPARTMENTS, HOURS, CONTACT, EMERGENCY"
                    )
                }
        except Exception as exc:
            return {"error": f"Could not retrieve hospital info: {exc}"}

    async def _get_departments(self, context: ToolContext) -> dict[str, Any]:
        from sqlalchemy import and_, select
        from app.modules.departments.models import Department

        result = await context.db.execute(
            select(Department.id, Department.name, Department.description).where(
                and_(
                    Department.hospital_id == context.hospital_id,
                    Department.is_active == True,  # noqa: E712
                )
            ).order_by(Department.name.asc())
        )
        rows = result.all()
        return {
            "departments": [
                {"id": str(r.id), "name": r.name, "description": r.description}
                for r in rows
            ],
            "total": len(rows),
        }

    def _get_hours(self, context: ToolContext) -> dict[str, Any]:
        config = context.hospital_config
        return {
            "timezone": context.timezone,
            "hours": config.get("operating_hours", {
                "monday_friday": "8:00 AM – 8:00 PM",
                "saturday": "9:00 AM – 5:00 PM",
                "sunday": "Emergency only",
            }),
        }

    def _get_contact(self, context: ToolContext) -> dict[str, Any]:
        cfg = context.hospital_config
        return {
            "phone": cfg.get("phone"),
            "email": cfg.get("email"),
            "address": cfg.get("address"),
            "website": cfg.get("website"),
        }

    def _get_emergency(self, context: ToolContext) -> dict[str, Any]:
        cfg = context.hospital_config
        return {
            "emergency_number": cfg.get("emergency_phone", "112"),
            "message": (
                "For medical emergencies, call "
                + cfg.get("emergency_phone", "112")
                + " immediately or proceed to the nearest Emergency Room. "
                "Do NOT wait for an appointment."
            ),
        }
