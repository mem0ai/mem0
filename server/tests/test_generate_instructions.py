"""Regression tests for LLM response parsing in POST /generate-instructions."""

import main
from main import GenerateInstructionsRequest, generate_instructions


class _StubLLM:
    def __init__(self, text):
        self._text = text

    def generate_response(self, messages):
        return self._text


class _StubMemory:
    def __init__(self, text):
        self.llm = _StubLLM(text)


def _run(monkeypatch, response_text):
    monkeypatch.setattr(main, "get_memory_instance", lambda: _StubMemory(response_text))
    return generate_instructions(GenerateInstructionsRequest(use_case="trip planning"), _auth=None)


def test_test_message_keeps_full_text_when_marker_recurs(monkeypatch):
    # The model echoes the literal marker inside the test message. Splitting on
    # every occurrence would truncate it; only the first split should count.
    resp = "INSTRUCTIONS: Focus on travel.\nTEST_MESSAGE: I typed TEST_MESSAGE: by mistake."
    out = _run(monkeypatch, resp)
    assert out["test_message"] == "I typed TEST_MESSAGE: by mistake."


def test_instructions_body_keeps_inner_label_occurrences(monkeypatch):
    # Only the leading INSTRUCTIONS: label should be stripped, not every
    # occurrence in the body.
    resp = "INSTRUCTIONS: see INSTRUCTIONS: below\nTEST_MESSAGE: hello"
    out = _run(monkeypatch, resp)
    assert out["custom_instructions"] == "see INSTRUCTIONS: below"
