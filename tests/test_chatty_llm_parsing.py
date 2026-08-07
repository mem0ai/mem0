"""Tests for chatty LLM JSON parsing robustness.

Validates that extract_json and the full fallback chain correctly handle
responses from local LLMs (LM Studio, Ollama) that wrap JSON in
conversational text, markdown code blocks, or both.
"""

import json

import pytest

from mem0.memory.utils import extract_json, remove_code_blocks


# --- Test extract_json ---

class TestExtractJson:
    """Tests for extract_json utility."""

    def test_pure_json(self):
        text = '{"memory": [{"id": "0", "text": "likes basketball", "event": "ADD"}]}'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes basketball"

    def test_json_in_markdown_code_block(self):
        text = '```json\n{"memory": [{"id": "0", "text": "likes basketball", "event": "ADD"}]}\n```'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes basketball"

    def test_json_in_plain_code_block(self):
        text = '```\n{"memory": [{"id": "0", "text": "likes basketball", "event": "ADD"}]}\n```'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes basketball"

    def test_chatty_with_markdown(self):
        """extract_json can handle embedded code blocks via re.search."""
        text = """Here is the extracted memory:
```json
{"memory": [{"id": "0", "text": "likes basketball", "event": "ADD"}]}
```
I hope this helps!"""
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes basketball"

    def test_chatty_without_markdown(self):
        """extract_json finds JSON by {/} boundaries when no code block is present."""
        text = """Here is the memory update you requested:
{"memory": [{"id": "0", "text": "likes gaming", "event": "ADD"}]}
That's the result."""
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes gaming"

    def test_chatty_multiline_json_without_markdown(self):
        """extract_json finds multi-line JSON by {/} boundaries."""
        text = """Here is the memory update:
{
  "memory": [
    {
      "id": "0",
      "text": "User likes gaming",
      "event": "ADD"
    }
  ]
}
"""
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "User likes gaming"

    def test_no_json_at_all(self):
        """No JSON in the text — should return as-is."""
        text = "I don't have any memory updates."
        result = extract_json(text)
        assert result == text

    def test_whitespace_padding(self):
        text = '  \n  {"memory": []}  \n  '
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed == {"memory": []}

    def test_nested_json_objects(self):
        """JSON with nested objects should find outermost braces."""
        text = 'Sure! {"memory": [{"id": "0", "text": "test", "event": "ADD"}]} Done.'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["id"] == "0"

    def test_chatty_with_braces_in_prose(self):
        """Prose containing braces before the real JSON must not defeat
        extraction (issue #5998)."""
        text = (
            'Based on the conversation {about travel}, here is the update: '
            '{"memory": [{"id": "0", "text": "likes travel", "event": "ADD"}]}'
        )
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes travel"

    def test_braces_in_prose_both_sides(self):
        """Brace-containing prose on both sides of the JSON payload."""
        text = (
            'Context {topic: travel}: {"memory": [{"id": "1", "text": "likes hiking", '
            '"event": "ADD"}]} -- note {end of update}.'
        )
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes hiking"

    def test_brace_inside_json_string_value(self):
        """Braces inside a JSON string literal must not break balancing."""
        text = 'Here: {"memory": [{"id": "0", "text": "use {curly} braces", "event": "ADD"}]}'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "use {curly} braces"

    def test_standalone_json_in_prose_preamble(self):
        """A standalone valid-JSON object in the prose preamble (schema echo,
        config example) must not be returned instead of the payload (#5998)."""
        text = (
            'Config {"a": 1} then memory: '
            '{"memory": [{"id": "0", "text": "likes travel", "event": "ADD"}]}'
        )
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "likes travel"

    def test_facts_payload_after_json_preamble(self):
        """The payload object may carry a 'facts' key; still preferred over a
        standalone object in the preamble."""
        text = 'Example {"schema": true}. Result: {"facts": ["likes hiking"]}'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["facts"] == ["likes hiking"]

    def test_long_brace_run_is_linear(self):
        """A long unbalanced-brace run must not make extraction quadratic
        (raw_decode keeps the scan linear per candidate)."""
        import time

        payload = '{"memory": [{"id": "0", "text": "ok", "event": "ADD"}]}'
        text = "{" * 40000 + " " + payload
        start = time.perf_counter()
        result = extract_json(text)
        elapsed = time.perf_counter() - start
        parsed = json.loads(result)
        assert parsed["memory"][0]["text"] == "ok"
        assert elapsed < 2.0, f"extract_json too slow on brace run: {elapsed:.2f}s"


# --- Test remove_code_blocks ---

class TestRemoveCodeBlocks:
    """Tests for remove_code_blocks — verify it does NOT handle chatty text."""

    def test_clean_code_block(self):
        text = '```json\n{"memory": []}\n```'
        result = remove_code_blocks(text)
        parsed = json.loads(result)
        assert parsed == {"memory": []}

    def test_no_code_block(self):
        """Without code blocks, returns content as-is (may not be valid JSON)."""
        text = 'Here is the result: {"memory": []}'
        result = remove_code_blocks(text)
        # This should NOT be parseable as JSON because it has leading text
        with pytest.raises(json.JSONDecodeError):
            json.loads(result)

    def test_think_tags_removed_inside_code_block(self):
        """Think tags inside a code block response are removed."""
        text = '```json\n<think>reasoning here</think>\n{"memory": []}\n```'
        result = remove_code_blocks(text)
        parsed = json.loads(result)
        assert parsed == {"memory": []}

    def test_think_tags_before_code_block_not_handled(self):
        """Think tags before code block cause regex to miss — fallback needed.

        This is a known limitation of remove_code_blocks: it matches the code
        block regex first, and only strips think tags from the result. When
        think tags come before the code block, the regex fails entirely.
        The fallback chain (extract_json) handles this case.
        """
        text = '<think>reasoning here</think>\n```json\n{"memory": []}\n```'
        result = remove_code_blocks(text)
        with pytest.raises(json.JSONDecodeError):
            json.loads(result)


# --- Test the full fallback chain (remove_code_blocks -> extract_json) ---

class TestFallbackChain:
    """Tests the actual fallback pattern used in _add_to_vector_store:
    try json.loads(remove_code_blocks(response))
    except JSONDecodeError: json.loads(extract_json(response))
    """

    def _parse_with_fallback(self, response):
        """Mimics the parsing logic in _add_to_vector_store."""
        try:
            return json.loads(remove_code_blocks(response), strict=False)
        except json.JSONDecodeError:
            extracted = extract_json(response)
            return json.loads(extracted, strict=False)

    def test_clean_json(self):
        response = '{"memory": [{"id": "0", "text": "Name is Alex", "event": "ADD"}]}'
        result = self._parse_with_fallback(response)
        assert result["memory"][0]["text"] == "Name is Alex"

    def test_markdown_wrapped(self):
        response = '```json\n{"memory": [{"id": "0", "text": "Name is Alex", "event": "ADD"}]}\n```'
        result = self._parse_with_fallback(response)
        assert result["memory"][0]["text"] == "Name is Alex"

    def test_chatty_markdown(self):
        """Issue #3788: LLM wraps in conversational text + markdown."""
        response = """Here is the extracted memory:
```json
{
  "memory": [
    {"id": "0", "text": "Name is Alex", "event": "ADD"},
    {"id": "1", "text": "Love basketball", "event": "ADD"},
    {"id": "2", "text": "Love gaming", "event": "ADD"}
  ]
}
```
I hope this helps!"""
        result = self._parse_with_fallback(response)
        assert len(result["memory"]) == 3
        assert result["memory"][0]["text"] == "Name is Alex"
        assert result["memory"][1]["text"] == "Love basketball"
        assert result["memory"][2]["text"] == "Love gaming"

    def test_chatty_no_markdown(self):
        """Issue #3788: LLM wraps in conversational text without markdown."""
        response = """Here is the memory update you requested:
{
  "memory": [
    {"id": "0", "text": "Name is Alex", "event": "ADD"},
    {"id": "1", "text": "Love basketball", "event": "ADD"}
  ]
}"""
        result = self._parse_with_fallback(response)
        assert len(result["memory"]) == 2

    def test_think_tags_with_json(self):
        """Reasoning model with <think> tags."""
        response = '<think>Let me process this...</think>\n```json\n{"memory": [{"id": "0", "text": "test", "event": "ADD"}]}\n```'
        result = self._parse_with_fallback(response)
        assert result["memory"][0]["text"] == "test"

    def test_lmstudio_style_response(self):
        """Mimics the actual LM Studio response format from the issue."""
        response = """{
  "memory": [
    {
      "id": "0",
      "text": "Name is Alex",
      "event": "ADD"
    },
    {
      "id": "1",
      "text": "Love basketball",
      "event": "ADD"
    },
    {
      "id": "2",
      "text": "Love gaming",
      "event": "ADD"
    }
  ]
}"""
        result = self._parse_with_fallback(response)
        assert len(result["memory"]) == 3

    def test_completely_invalid_response(self):
        """If both attempts fail, the outer except in main.py catches it."""
        response = "I don't understand the question"
        with pytest.raises(json.JSONDecodeError):
            self._parse_with_fallback(response)

    def test_facts_extraction_fallback(self):
        """Also verify the pattern works for facts extraction responses."""
        response = 'Sure! Here are the facts:\n{"facts": ["Name is Alex", "Loves basketball"]}\nHope that helps!'
        result = self._parse_with_fallback(response)
        assert result["facts"] == ["Name is Alex", "Loves basketball"]
