"""
GeminiGateway — the async Gemini API client with tool-calling agentic loop.

ARCHITECTURE (ADR-003):
  - This is the ONLY place in the codebase that talks to the Gemini API.
  - All LLM responses pass through SafetyLayer before being returned.
  - All tool calls are executed through ToolRegistry (never directly by the LLM).
  - The agentic loop is capped at MAX_TOOL_ITERATIONS to prevent runaway calls.

Gemini API notes:
  - Uses google-generativeai SDK (google.generativeai)
  - asyncio.to_thread() wraps sync SDK calls for FastAPI compatibility
  - Function calling uses genai.protos for structured function call/response parts
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Graceful import — app runs without Gemini if API key not configured
try:
    import google.generativeai as genai
    import google.generativeai.protos as genai_protos
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False
    logger.warning("google_generativeai_not_installed", hint="pip install google-generativeai>=0.8.0")


@dataclass
class GatewayResponse:
    """Structured response from the agentic loop."""
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    safety_flags: list[str] = field(default_factory=list)
    fallback_used: bool = False


class GeminiGateway:
    """
    Thin async wrapper around the Gemini GenerativeModel API.

    Usage:
        gateway = GeminiGateway(api_key="...", model_name="gemini-1.5-flash")
        response = await gateway.run(
            system_prompt=...,
            history=...,
            user_message=...,
            context=...,
            registry=...,
            max_iterations=6,
        )
    """

    _FALLBACK_RESPONSE = (
        "I'm sorry, I wasn't able to process your request right now. "
        "Please try again or contact our reception team directly."
    )

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._configured = False

    def _ensure_configured(self) -> None:
        if not _GEMINI_AVAILABLE:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai>=0.8.0"
            )
        if not self._configured:
            genai.configure(api_key=self._api_key)
            self._configured = True

    async def run(
        self,
        system_prompt: str,
        history: list[dict[str, Any]],
        user_message: str,
        context: "ToolContext",  # type: ignore[name-defined]
        registry: "ToolRegistry",  # type: ignore[name-defined]
        temperature: float = 0.4,
        max_output_tokens: int = 1024,
        max_iterations: int = 6,
    ) -> GatewayResponse:
        """
        Run the full agentic loop:
        1. Initialize Gemini model with tool declarations
        2. Start chat with conversation history
        3. Send user message
        4. If model requests tool calls → execute via registry → feed results back
        5. Repeat until text response or max_iterations reached
        """
        if not self._api_key:
            logger.warning("gemini_api_key_not_configured")
            return GatewayResponse(
                text="The AI assistant is not currently configured. Please contact reception.",
                fallback_used=True,
            )

        try:
            self._ensure_configured()
        except RuntimeError as e:
            return GatewayResponse(text=str(e), fallback_used=True)

        try:
            tool_declarations = registry.get_function_declarations()

            # Build Gemini model with tools
            model = await asyncio.to_thread(
                genai.GenerativeModel,
                model_name=self._model_name,
                tools=tool_declarations if tool_declarations else None,
                system_instruction=system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    candidate_count=1,
                ),
            )

            # Convert stored history to Gemini Content format
            gemini_history = self._build_gemini_history(history)

            chat = await asyncio.to_thread(
                model.start_chat, history=gemini_history
            )

            all_tool_calls: list[dict[str, Any]] = []
            iterations = 0
            current_message: Any = user_message

            for iteration in range(max_iterations):
                iterations = iteration + 1

                # Send message (user text or tool responses)
                response = await asyncio.to_thread(chat.send_message, current_message)

                # Check if response has function calls
                fn_call_parts = [
                    part for part in response.parts
                    if hasattr(part, "function_call") and part.function_call
                ]

                if not fn_call_parts:
                    # Pure text response — loop complete
                    text = response.text or ""
                    logger.info(
                        "gemini_response_received",
                        iterations=iterations,
                        tool_calls_made=len(all_tool_calls),
                        text_length=len(text),
                    )
                    return GatewayResponse(
                        text=text,
                        tool_calls=all_tool_calls,
                        iterations=iterations,
                    )

                # Execute all tool calls in this response
                tool_response_parts = []
                for part in fn_call_parts:
                    fc = part.function_call
                    fn_name = fc.name
                    fn_args = dict(fc.args) if fc.args else {}

                    logger.info(
                        "tool_call_requested",
                        tool=fn_name,
                        iteration=iteration + 1,
                    )

                    result = await registry.execute(fn_name, fn_args, context)

                    all_tool_calls.append({
                        "name": fn_name,
                        "input": fn_args,
                        "output": result,
                        "executed_at": datetime.now(UTC).isoformat(),
                    })

                    # Build function response part for Gemini
                    tool_response_parts.append(
                        genai_protos.Part(
                            function_response=genai_protos.FunctionResponse(
                                name=fn_name,
                                response={"result": result},
                            )
                        )
                    )

                # Send tool results back to the model
                current_message = genai_protos.Content(parts=tool_response_parts)

            # Max iterations reached without text response
            logger.warning(
                "gemini_max_iterations_reached",
                max_iterations=max_iterations,
                tool_calls=len(all_tool_calls),
            )
            return GatewayResponse(
                text=self._FALLBACK_RESPONSE,
                tool_calls=all_tool_calls,
                iterations=iterations,
                fallback_used=True,
            )

        except Exception as exc:
            logger.exception("gemini_gateway_error", error=str(exc))
            return GatewayResponse(
                text=self._FALLBACK_RESPONSE,
                tool_calls=[],
                fallback_used=True,
            )

    @staticmethod
    def _build_gemini_history(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert stored conversation messages to Gemini history format.
        Only USER and ASSISTANT messages are included in history.
        TOOL records are stored in DB for audit but excluded from LLM context.
        """
        gemini_history = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                gemini_history.append({
                    "role": "user",
                    "parts": [{"text": content}],
                })
            elif role == "assistant":
                gemini_history.append({
                    "role": "model",
                    "parts": [{"text": content}],
                })
            # Skip TOOL and SYSTEM messages — not part of Gemini chat history

        return gemini_history
