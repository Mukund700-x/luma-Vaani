"""
Unit tests for the notification template renderer (Phase 6).

Pure Python — no DB, no external services.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "api"))

from app.modules.notifications.renderer import render_template, safe_render


SAMPLE_CONTEXT = {
    "patient_name": "Ravi",
    "patient_full_name": "Ravi Kumar Joshi",
    "doctor_name": "Dr. Arjun Sharma",
    "department": "Cardiology",
    "hospital_name": "Luma Demo Hospital",
    "appointment_date": "Monday, 06 October 2026",
    "appointment_time": "10:30 AM",
    "appointment_ref": "A1B2C3D4",
    "cancellation_reason": "",
    "emergency_number": "+91-9999999911",
}


class TestRenderTemplate:

    def test_simple_variable_substitution(self):
        tmpl = "Hello {{ patient_name }}!"
        result = render_template(tmpl, SAMPLE_CONTEXT)
        assert result == "Hello Ravi!"

    def test_multiple_variables(self):
        tmpl = "{{ doctor_name }} at {{ department }}"
        result = render_template(tmpl, SAMPLE_CONTEXT)
        assert result == "Dr. Arjun Sharma at Cardiology"

    def test_missing_variable_raises(self):
        tmpl = "Hello {{ nonexistent_variable }}!"
        with pytest.raises(ValueError, match="Missing template variable"):
            render_template(tmpl, SAMPLE_CONTEXT)

    def test_syntax_error_raises(self):
        tmpl = "Hello {% invalid %}"
        with pytest.raises(ValueError):
            render_template(tmpl, SAMPLE_CONTEXT)

    def test_empty_template_returns_empty(self):
        result = render_template("", SAMPLE_CONTEXT)
        assert result == ""

    def test_template_no_variables(self):
        tmpl = "Static message with no placeholders."
        result = render_template(tmpl, SAMPLE_CONTEXT)
        assert result == tmpl

    def test_appointment_ref_rendered(self):
        tmpl = "Ref: {{ appointment_ref }}"
        result = render_template(tmpl, SAMPLE_CONTEXT)
        assert result == "Ref: A1B2C3D4"


class TestSafeRender:

    def test_missing_variable_returns_raw_template(self):
        """safe_render must never crash — returns raw template on failure."""
        tmpl = "Hello {{ missing_var }}!"
        result = safe_render(tmpl, SAMPLE_CONTEXT)
        assert result == tmpl   # Returns original template, not empty string

    def test_valid_template_renders_normally(self):
        tmpl = "Dear {{ patient_name }}, your appointment is confirmed."
        result = safe_render(tmpl, SAMPLE_CONTEXT)
        assert "Ravi" in result
        assert "confirmed" in result

    def test_never_raises(self):
        """safe_render must never raise under any circumstances."""
        bad_templates = [
            "{% for x in %}",   # syntax error
            "{{ missing }}",    # undefined
            "",                 # empty
            "{{ patient_name }}" * 1000,  # very long
        ]
        for tmpl in bad_templates:
            try:
                result = safe_render(tmpl, SAMPLE_CONTEXT)
                assert isinstance(result, str)
            except Exception as e:
                pytest.fail(f"safe_render raised an exception: {e}")
