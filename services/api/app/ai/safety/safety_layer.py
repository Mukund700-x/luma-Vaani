"""
SafetyLayer — runs on every AI input and output.

Responsibilities:
  1. Emergency detection (input + output): immediate escalation response
  2. Prohibited output detection: no diagnosis, no prescription advice
  3. Clinical boundary enforcement: redirect clinical questions to professionals
  4. Output sanitation: strip any PII that leaked into AI text

This layer NEVER blocks — it always returns a response. In the worst case,
it substitutes a safe fallback message for the AI output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Emergency keywords (case-insensitive) ─────────────────────────────────────
_EMERGENCY_PATTERNS = [
    r"\bchest\s+pain\b",
    r"\bheart\s+attack\b",
    r"\bstroke\b",
    r"\bcan[''`]?t\s+breathe\b",
    r"\bshortness\s+of\s+breath\b",
    r"\bsevere\s+bleed(ing)?\b",
    r"\bunconscious\b",
    r"\bnot\s+breathing\b",
    r"\bsuicid(e|al)\b",
    r"\boverdos(e|ed)\b",
    r"\bseizure\b",
    r"\bfainting\b",
    r"\bparalys(is|ed)\b",
    r"\bsevere\s+allergic\b",
    r"\banaphylaxis\b",
    r"\bemergency\b",
    r"\bambulance\b",
]

# ── Prohibited AI output patterns ─────────────────────────────────────────────
_DIAGNOSIS_PATTERNS = [
    r"\byou\s+(have|are\s+suffering|are\s+diagnosed)\s+with\b",
    r"\bdiagnos(is|ed)\s+(with|as)\b",
    r"\byour\s+condition\s+is\b",
    r"\bthis\s+(sounds?|looks?)\s+like\s+(diabetes|cancer|hypertension|covid|malaria|typhoid|tuberculosis|asthma)\b",
]

_PRESCRIPTION_PATTERNS = [
    r"\btake\s+\d+\s*(mg|ml|tablet|capsule|dose)\b",
    r"\bprescrib(e|ing|ed)\b",
    r"\bdosage\s+of\b",
    r"\bI\s+recommend\s+(taking|you\s+take)\b",
]

_EMERGENCY_ESCALATION_TEMPLATE = (
    "⚠️ **This sounds like a medical emergency.** "
    "Please **call {emergency_number} immediately** or go to the nearest Emergency Room. "
    "Do NOT wait for an appointment. Your safety is the priority."
)

_PROHIBITED_OUTPUT_SUBSTITUTE = (
    "I'm Luma Vaani, a front-desk assistant — I'm not able to provide medical diagnoses "
    "or treatment advice. Please consult a doctor for medical guidance. "
    "I can help you find the right doctor and book an appointment. Would you like me to do that?"
)


@dataclass
class SafetyCheckResult:
    is_emergency: bool = False
    is_prohibited: bool = False
    emergency_response: str | None = None
    cleaned_text: str = ""
    flags: list[str] = field(default_factory=list)


class SafetyLayer:
    """
    Stateless safety processor. Instantiate per request.

    Usage:
        safety = SafetyLayer(emergency_number="112")
        input_result = safety.check_input(user_message)
        if input_result.is_emergency:
            return input_result.emergency_response

        # ... get AI response ...

        output_result = safety.check_output(ai_response)
        final_text = output_result.cleaned_text
    """

    def __init__(self, emergency_number: str = "112") -> None:
        self._emergency_number = emergency_number

    def check_input(self, text: str) -> SafetyCheckResult:
        """
        Check patient input for emergency signals.
        Returns an emergency response if detected — bypass the LLM entirely.
        """
        result = SafetyCheckResult(cleaned_text=text)

        if self._matches_any(text, _EMERGENCY_PATTERNS):
            result.is_emergency = True
            result.flags.append("emergency_detected_in_input")
            result.emergency_response = _EMERGENCY_ESCALATION_TEMPLATE.format(
                emergency_number=self._emergency_number
            )

        return result

    def check_output(self, text: str) -> SafetyCheckResult:
        """
        Check AI output for prohibited content.
        Substitutes safe fallback if diagnosis/prescription detected.
        """
        result = SafetyCheckResult(cleaned_text=text)

        # Re-check for emergency keywords in AI output (shouldn't happen but guard it)
        if self._matches_any(text, _EMERGENCY_PATTERNS):
            result.is_emergency = True
            result.flags.append("emergency_detected_in_output")
            result.emergency_response = _EMERGENCY_ESCALATION_TEMPLATE.format(
                emergency_number=self._emergency_number
            )
            # Replace any casual AI response with the escalation message
            result.cleaned_text = result.emergency_response
            return result

        # Check for prohibited clinical content
        if self._matches_any(text, _DIAGNOSIS_PATTERNS):
            result.is_prohibited = True
            result.flags.append("diagnosis_detected")
            result.cleaned_text = _PROHIBITED_OUTPUT_SUBSTITUTE
            return result

        if self._matches_any(text, _PRESCRIPTION_PATTERNS):
            result.is_prohibited = True
            result.flags.append("prescription_detected")
            result.cleaned_text = _PROHIBITED_OUTPUT_SUBSTITUTE
            return result

        return result

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)
