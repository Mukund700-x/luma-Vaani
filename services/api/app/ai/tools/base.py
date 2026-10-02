"""
AI Tool layer foundation.

Architecture (ADR-003 compliant):
  - AITool: abstract base class for every tool the LLM can invoke
  - ToolContext: request-scoped context passed to every tool execution
  - ToolCallRecord: immutable audit record of a single tool invocation
  - ToolRegistry: maps Gemini function names → AITool implementations

IMPORTANT RULES:
  1. Every tool MUST be tenant-scoped (hospital_id enforced inside execute())
  2. Tools NEVER return raw DB rows — only typed dicts the LLM can reason about
  3. Tools NEVER perform write operations that bypass the service layer
  4. All tool inputs are validated; invalid inputs return {"error": "..."} not exceptions
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class ToolContext:
    """
    Request-scoped context injected into every tool execution.
    Mutable — the find_patient tool may set patient_id after lookup.
    """

    hospital_id: uuid.UUID
    conversation_id: uuid.UUID
    db: AsyncSession
    hospital_config: dict[str, Any]  # hospital.config JSONB

    # May be None for anonymous conversations; set by find_patient tool
    patient_id: uuid.UUID | None = None

    # Accumulates updates to propagate back to the conversation record
    _updates: dict[str, Any] = field(default_factory=dict)

    def set_patient(self, patient_id: uuid.UUID) -> None:
        """Called by find_patient tool after a successful lookup."""
        self.patient_id = patient_id
        self._updates["patient_id"] = patient_id

    @property
    def timezone(self) -> str:
        return self.hospital_config.get("timezone", "Asia/Kolkata")

    @property
    def language(self) -> str:
        return self.hospital_config.get("default_language", "en")


@dataclass(frozen=True)
class ToolCallRecord:
    """
    Immutable audit record of a single tool invocation.
    Persisted to conversation_messages (role=TOOL) after each AI turn.
    """

    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    success: bool
    duration_ms: float
    executed_at: datetime = field(default_factory=datetime.utcnow)


class AITool(ABC):
    """
    Abstract base class for all AI-invocable tools.

    Subclasses MUST implement:
        - name (str): matches the Gemini function declaration name
        - description (str): shown to the LLM — clear, action-oriented
        - parameters (dict): JSON Schema for the function's parameters
        - execute(**kwargs): the actual implementation

    Subclasses SHOULD:
        - Handle all errors gracefully (return {"error": "..."} instead of raising)
        - Never log PHI (patient names, phone numbers, DoB)
        - Enforce hospital_id scoping on every DB query
    """

    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(self, context: ToolContext, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the tool and return a dict the LLM can reason about.
        Must never raise — catch all exceptions and return {"error": "..."}.
        """
        ...

    def to_function_declaration(self) -> dict[str, Any]:
        """Returns the Gemini-compatible function declaration dict."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """
    Central registry that maps tool names to AITool implementations.
    Handles execution with timeout enforcement and structured logging.
    """

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._tools: dict[str, AITool] = {}
        self._timeout = timeout_seconds

    def register(self, tool: AITool) -> "ToolRegistry":
        """Register a tool. Returns self for fluent chaining."""
        self._tools[tool.name] = tool
        logger.debug("tool_registered", name=tool.name)
        return self

    def get_function_declarations(self) -> list[dict[str, Any]]:
        """Returns all tool declarations for Gemini model initialization."""
        return [t.to_function_declaration() for t in self._tools.values()]

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        context: ToolContext,
    ) -> dict[str, Any]:
        """
        Execute a named tool with the given arguments.
        Enforces per-tool timeout. Returns {"error": "..."} for all failures.
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("unknown_tool_call", name=name)
            return {"error": f"Unknown tool: '{name}'"}

        start = asyncio.get_event_loop().time()
        try:
            result = await asyncio.wait_for(
                tool.execute(context, **args),
                timeout=self._timeout,
            )
            duration_ms = (asyncio.get_event_loop().time() - start) * 1000
            logger.info(
                "tool_executed",
                tool=name,
                duration_ms=round(duration_ms, 1),
                hospital_id=str(context.hospital_id),
                success=True,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("tool_timeout", tool=name, timeout=self._timeout)
            return {"error": f"Tool '{name}' timed out. Please try again."}
        except Exception as exc:
            logger.exception("tool_error", tool=name, error=str(exc))
            return {"error": f"Tool '{name}' failed. Please try again."}


def build_default_registry(timeout_seconds: float = 10.0) -> ToolRegistry:
    """
    Build and return the fully-wired ToolRegistry with all enabled tools.
    Called once per conversation turn (cheap — just dict assignments).
    """
    from app.ai.tools.implementations.find_patient import FindPatientTool
    from app.ai.tools.implementations.search_doctors import SearchDoctorsTool
    from app.ai.tools.implementations.get_availability import GetAvailabilityTool
    from app.ai.tools.implementations.book_appointment import BookAppointmentTool
    from app.ai.tools.implementations.manage_appointments import (
        GetPatientAppointmentsTool,
        CancelAppointmentTool,
    )
    from app.ai.tools.implementations.hospital_info import GetHospitalInfoTool
    from app.ai.tools.implementations.search_knowledge import SearchKnowledgeTool

    registry = ToolRegistry(timeout_seconds=timeout_seconds)
    (
        registry
        .register(FindPatientTool())
        .register(SearchDoctorsTool())
        .register(GetAvailabilityTool())
        .register(BookAppointmentTool())
        .register(GetPatientAppointmentsTool())
        .register(CancelAppointmentTool())
        .register(GetHospitalInfoTool())
        # Phase 5: RAG — hospital knowledge base
        .register(SearchKnowledgeTool())
    )
    return registry
