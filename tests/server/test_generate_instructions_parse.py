"""Unit tests for /generate-instructions response parsing (#5993)."""

import sys
from pathlib import Path

# Allow importing the lightweight helper without loading the FastAPI app.
SERVER_DIR = Path(__file__).resolve().parents[2] / "server"
sys.path.insert(0, str(SERVER_DIR))

from instruction_parse import parse_generate_instructions_response  # noqa: E402


class TestParseGenerateInstructionsResponse:
    def test_happy_path(self):
        raw = (
            "INSTRUCTIONS: Capture hiking preferences and gear notes.\n"
            "TEST_MESSAGE: I want a lighter backpack for weekend hikes."
        )
        out = parse_generate_instructions_response(raw)
        assert out["custom_instructions"] == "Capture hiking preferences and gear notes."
        assert out["test_message"] == "I want a lighter backpack for weekend hikes."

    def test_interior_instructions_marker_preserved(self):
        # Global .replace("INSTRUCTIONS:", "") would destroy the interior marker.
        raw = (
            "INSTRUCTIONS: Please follow these INSTRUCTIONS: prioritize recent events.\n"
            "TEST_MESSAGE: Remember this TEST_MESSAGE: hello."
        )
        out = parse_generate_instructions_response(raw)
        assert out["custom_instructions"] == (
            "Please follow these INSTRUCTIONS: prioritize recent events."
        )
        assert out["test_message"] == "Remember this TEST_MESSAGE: hello."

    def test_interior_test_message_marker_in_instructions(self):
        raw = (
            "INSTRUCTIONS: Never echo TEST_MESSAGE: labels back to the user.\n"
            "TEST_MESSAGE: I book flights every March."
        )
        out = parse_generate_instructions_response(raw)
        assert "TEST_MESSAGE: labels" in out["custom_instructions"]
        assert out["test_message"] == "I book flights every March."

    def test_preamble_before_instructions(self):
        raw = (
            "Sure — here you go:\n"
            "INSTRUCTIONS: Track dietary restrictions narrowly.\n"
            "TEST_MESSAGE: I am allergic to peanuts."
        )
        out = parse_generate_instructions_response(raw)
        assert out["custom_instructions"] == "Track dietary restrictions narrowly."
        assert out["test_message"] == "I am allergic to peanuts."

    def test_missing_markers_returns_raw_with_default_test(self):
        raw = "unstructured blob with no labels"
        out = parse_generate_instructions_response(raw)
        assert out["custom_instructions"] == raw
        assert out["test_message"] == "I like to hike on weekends."

    def test_custom_default_test_message(self):
        out = parse_generate_instructions_response(
            "no labels here", default_test_message="fallback"
        )
        assert out["test_message"] == "fallback"

    def test_none_response(self):
        out = parse_generate_instructions_response(None)
        assert out["custom_instructions"] == ""
        assert out["test_message"] == "I like to hike on weekends."
