"""Tests for robust fact extraction JSON parsing.

Covers:
- sanitize_json_string: invalid UTF-16 surrogate escape handling
- parse_facts_from_response: end-to-end parsing with sanitization and retry
"""

import json
from unittest.mock import MagicMock

import pytest

from mem0.memory.utils import parse_facts_from_response, sanitize_json_string


# ---------------------------------------------------------------------------
# sanitize_json_string
# ---------------------------------------------------------------------------

class TestSanitizeJsonString:
    def test_lone_high_surrogate_replaced(self):
        """Lone high surrogate (\\uD800-\\uDBFF) should be replaced."""
        text = r'{"facts": ["User likes \uD83D pizza"]}'
        result = sanitize_json_string(text)
        assert r"\uD83D" not in result
        assert "\ufffd" in result

    def test_lone_low_surrogate_replaced(self):
        """Lone low surrogate (\\uDC00-\\uDFFF) should be replaced."""
        text = r'{"facts": ["Test \uDE00 value"]}'
        result = sanitize_json_string(text)
        assert r"\uDE00" not in result
        assert "\ufffd" in result

    def test_surrogate_pair_replaced(self):
        """A full surrogate pair (high + low) should be replaced as one unit."""
        # \uD83D\uDE00 is the surrogate pair for 😀
        text = r'{"facts": ["emoji \uD83D\uDE00 here"]}'
        result = sanitize_json_string(text)
        assert r"\uD83D" not in result
        assert r"\uDE00" not in result
        # Should produce exactly one replacement char for the pair
        assert result.count("\ufffd") == 1

    def test_valid_unicode_escapes_preserved(self):
        """Normal unicode escapes (non-surrogate) should be left intact."""
        text = r'{"facts": ["User speaks \u4e2d\u6587"]}'
        result = sanitize_json_string(text)
        assert result == text  # No change

    def test_no_escapes_passthrough(self):
        """Plain strings without any unicode escapes pass through unchanged."""
        text = '{"facts": ["User likes Python"]}'
        result = sanitize_json_string(text)
        assert result == text

    def test_multiple_surrogates_all_replaced(self):
        """Multiple lone surrogates in the same string are all handled."""
        text = r'{"facts": ["\uD800 and \uDBFF and \uDC00"]}'
        result = sanitize_json_string(text)
        assert r"\uD800" not in result
        assert r"\uDBFF" not in result
        assert r"\uDC00" not in result

    def test_sanitized_output_is_valid_json(self):
        """After sanitization, the string should be parseable as JSON."""
        text = r'{"facts": ["User said \uD83D hello"]}'
        result = sanitize_json_string(text)
        parsed = json.loads(result)
        assert "facts" in parsed
        assert len(parsed["facts"]) == 1


# ---------------------------------------------------------------------------
# parse_facts_from_response
# ---------------------------------------------------------------------------

class TestParseFactsFromResponse:
    def test_valid_json_parsed(self):
        """Standard valid JSON response is parsed correctly."""
        response = '{"facts": ["User likes Python", "Lives in Tokyo"]}'
        facts = parse_facts_from_response(response)
        assert facts == ["User likes Python", "Lives in Tokyo"]

    def test_empty_response_returns_empty(self):
        """Empty or whitespace-only response returns empty list."""
        assert parse_facts_from_response("") == []
        assert parse_facts_from_response("   ") == []

    def test_empty_facts_array(self):
        """Response with empty facts array returns empty list."""
        assert parse_facts_from_response('{"facts": []}') == []

    def test_code_block_wrapped_json(self):
        """JSON wrapped in markdown code blocks is handled."""
        response = '```json\n{"facts": ["User prefers Vim"]}\n```'
        facts = parse_facts_from_response(response)
        assert facts == ["User prefers Vim"]

    def test_surrogate_escapes_sanitized_before_parse(self):
        r"""Invalid surrogate escapes (\uD800-\uDFFF) are cleaned before parsing."""
        # This would cause json.JSONDecodeError without sanitization
        response = r'{"facts": ["User name is \uD83D test"]}'
        facts = parse_facts_from_response(response)
        assert len(facts) == 1
        assert "\ufffd" in facts[0]  # Replacement char

    def test_chatty_output_with_json_extracted(self):
        """LLM response with prose around JSON is handled via extract_json fallback."""
        response = (
            "Here are the facts I extracted:\n\n"
            '```json\n{"facts": ["Prefers dark mode"]}\n```\n\n'
            "Let me know if you need more."
        )
        facts = parse_facts_from_response(response)
        assert facts == ["Prefers dark mode"]

    def test_dict_facts_normalized(self):
        """Facts returned as objects (common with smaller LLMs) are normalized."""
        response = '{"facts": [{"fact": "Uses VS Code"}, {"text": "Knows Rust"}]}'
        facts = parse_facts_from_response(response)
        assert facts == ["Uses VS Code", "Knows Rust"]

    def test_no_retry_by_default(self):
        """With max_retries=0 (default), a bad response fails immediately."""
        response = "this is not json at all"
        facts = parse_facts_from_response(response)
        assert facts == []

    def test_retry_succeeds_on_second_attempt(self):
        """When first response is bad, retry with LLM produces valid result."""
        bad_response = "totally broken json {"
        good_response = '{"facts": ["Recovered fact"]}'

        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = good_response

        facts = parse_facts_from_response(
            bad_response,
            max_retries=1,
            llm=mock_llm,
            system_prompt="sys",
            user_prompt="usr",
        )
        assert facts == ["Recovered fact"]
        mock_llm.generate_response.assert_called_once()

    def test_retry_all_attempts_fail(self):
        """When all retry attempts also produce bad JSON, returns empty list."""
        bad_response = "broken"

        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "still broken"

        facts = parse_facts_from_response(
            bad_response,
            max_retries=2,
            llm=mock_llm,
            system_prompt="sys",
            user_prompt="usr",
        )
        assert facts == []
        assert mock_llm.generate_response.call_count == 2

    def test_retry_not_attempted_without_llm(self):
        """If max_retries > 0 but no LLM provided, retries are skipped gracefully."""
        facts = parse_facts_from_response(
            "bad json",
            max_retries=3,
            llm=None,
        )
        assert facts == []

    def test_retry_llm_call_itself_fails(self):
        """If the LLM call during retry raises, we continue to next attempt."""
        mock_llm = MagicMock()
        mock_llm.generate_response.side_effect = [
            RuntimeError("API timeout"),
            '{"facts": ["Finally worked"]}',
        ]

        facts = parse_facts_from_response(
            "initial bad",
            max_retries=2,
            llm=mock_llm,
            system_prompt="sys",
            user_prompt="usr",
        )
        assert facts == ["Finally worked"]
        assert mock_llm.generate_response.call_count == 2

    def test_production_surrogate_scenario(self):
        """Realistic scenario from Cerebras Qwen3-235B producing invalid surrogates."""
        # Simulates the exact error pattern from the issue report
        response = (
            r'{"facts": ["用户的名字是\uD835\uDC00张三", '
            r'"User prefers \uD83D dark mode", '
            r'"Lives in Beijing"]}'
        )
        facts = parse_facts_from_response(response)
        assert len(facts) == 3
        assert "Lives in Beijing" in facts

    def test_think_tags_stripped(self):
        """<think> tags from reasoning models are stripped before parsing."""
        response = '<think>Let me analyze...</think>{"facts": ["User likes cats"]}'
        facts = parse_facts_from_response(response)
        assert facts == ["User likes cats"]
