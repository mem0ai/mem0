"""Tests for chatty LLM JSON parsing robustness.

Validates that extract_json and the full fallback chain correctly handle
responses from local LLMs (LM Studio, Ollama) that wrap JSON in
conversational text, markdown code blocks, or both.
"""

import json
from unittest.mock import MagicMock

import pytest

from mem0.memory.utils import (
    extract_json,
    llm_supports_tool_calls,
    parse_tool_calls_for_memory,
    recover_extraction_via_tools,
    remove_code_blocks,
)

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


class TestToolCallRecovery:
    """The forced-tool-call recovery used when no JSON could be parsed at all
    (full content-hijack - the case extract_json structurally cannot fix)."""

    def test_parse_tool_calls_extracts_memory_from_dict_arguments(self):
        response = {
            "content": None,
            "tool_calls": [{"name": "save_memories", "arguments": {"memory": [{"text": "Likes hiking"}]}}],
        }
        assert parse_tool_calls_for_memory(response) == [{"text": "Likes hiking"}]

    def test_parse_tool_calls_handles_stringified_arguments(self):
        response = {"tool_calls": [{"name": "save_memories", "arguments": '{"memory": [{"text": "Has a cat"}]}'}]}
        assert parse_tool_calls_for_memory(response) == [{"text": "Has a cat"}]

    def test_parse_tool_calls_returns_none_when_no_tool_call_parses(self):
        # A provider that ignored the tool and returned prose, or returned no
        # usable tool call, yields None - "could not parse", distinct from a
        # successfully parsed empty memory list.
        assert parse_tool_calls_for_memory("just some prose") is None
        assert parse_tool_calls_for_memory({"tool_calls": []}) is None

    def test_parse_tool_calls_distinguishes_valid_empty_from_unparseable(self):
        # {"memory": []} parsed cleanly is a real (empty) result, not a failure.
        parsed_empty = {"tool_calls": [{"name": "save_memories", "arguments": {"memory": []}}]}
        assert parse_tool_calls_for_memory(parsed_empty) == []
        # Truncated stringified arguments cannot parse -> None.
        truncated = {"tool_calls": [{"name": "save_memories", "arguments": '{"memory": [{"text": "cut of'}]}
        assert parse_tool_calls_for_memory(truncated) is None

    def test_parse_tool_calls_merges_parallel_tool_calls(self):
        # The tool description invites one call per fact; a model answering a
        # forced call with parallel invocations must not lose facts beyond the
        # first call (and a leading empty call must not mask later facts).
        response = {
            "tool_calls": [
                {"name": "save_memories", "arguments": {"memory": []}},
                {"name": "save_memories", "arguments": {"memory": [{"text": "Likes hiking"}]}},
                {"name": "save_memories", "arguments": {"memory": [{"text": "Has a cat"}]}},
            ]
        }
        assert parse_tool_calls_for_memory(response) == [{"text": "Likes hiking"}, {"text": "Has a cat"}]

    def test_parse_tool_calls_drops_non_dict_memory_items(self):
        # A schema-violating model can emit bare strings in the memory array.
        # Downstream reads m.get("text"), so non-dict items must be filtered
        # out here rather than crash add() - the recovery path must never make
        # things worse than the silent drop it replaces.
        response = {
            "tool_calls": [
                {"name": "save_memories", "arguments": {"memory": ["bare string", {"text": "Has a cat"}, 42]}}
            ]
        }
        assert parse_tool_calls_for_memory(response) == [{"text": "Has a cat"}]

    def test_gate_requires_explicit_true(self):
        # A MagicMock auto-populates attributes; the gate must not be tripped by one.
        assert llm_supports_tool_calls(MagicMock()) is False
        capable = MagicMock()
        capable.supports_tool_calls = True
        assert llm_supports_tool_calls(capable) is True

    def test_recover_skips_uncapable_provider_without_calling_llm(self):
        llm = MagicMock()
        llm.supports_tool_calls = False
        assert recover_extraction_via_tools(llm, "sys", "user") == []
        llm.generate_response.assert_not_called()

    def test_recover_forces_tool_choice_and_returns_memory(self):
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.generate_response.return_value = {
            "tool_calls": [{"name": "save_memories", "arguments": {"memory": [{"text": "Born in Pittsburgh"}]}}]
        }
        result = recover_extraction_via_tools(llm, "sys", "user")
        assert result == [{"text": "Born in Pittsburgh"}]
        call_kwargs = llm.generate_response.call_args.kwargs
        assert call_kwargs["tool_choice"] == "required"
        assert call_kwargs["tools"][0]["function"]["name"] == "save_memories"

    def test_recover_is_graceful_when_llm_raises(self):
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.generate_response.side_effect = RuntimeError("provider exploded")
        assert recover_extraction_via_tools(llm, "sys", "user") == []

    def test_recover_returns_empty_when_nothing_memorable_without_retrying(self):
        # A forced tool call with an empty memory array round-trips to [] -
        # the model is not compelled to invent a fact to satisfy the call. A
        # valid empty list is NOT treated as truncation: no token-raise retry,
        # exactly one LLM call.
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.config.max_tokens = 2000
        llm.generate_response.return_value = {"tool_calls": [{"name": "save_memories", "arguments": {"memory": []}}]}
        assert recover_extraction_via_tools(llm, "sys", "user") == []
        assert llm.generate_response.call_count == 1

    def test_recover_is_graceful_when_tool_calls_malformed(self):
        # A provider returning a non-dict tool_call must not raise - the
        # "recovery never raises" guarantee.
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.generate_response.return_value = {"tool_calls": ["not-a-dict", None]}
        assert recover_extraction_via_tools(llm, "sys", "user") == []

    def test_tool_call_truncation_retries_at_raised_tokens_staying_in_tool_mode(self):
        # The forced tool call itself truncates (its arguments are a cut-off JSON
        # string -> no memory parses). Recovery retries the tool call once at a
        # raised max_tokens, still forcing the tool (not reverting to free text).
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.config.max_tokens = 2000
        llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "save_memories", "arguments": '{"memory": [{"text": "User likes hik'}]},
            {"tool_calls": [{"name": "save_memories", "arguments": {"memory": [{"text": "User likes hiking"}]}}]},
        ]
        result = recover_extraction_via_tools(llm, "sys", "user")
        assert result == [{"text": "User likes hiking"}]
        assert llm.generate_response.call_count == 2
        # the retry is still a forced tool call, at 4x the configured budget
        retry_kwargs = llm.generate_response.call_args_list[1].kwargs
        assert retry_kwargs["tool_choice"] == "required"
        assert retry_kwargs["max_tokens"] == 8000

    def test_no_token_raise_retry_when_max_tokens_unset(self):
        # If max_tokens is unset there is nothing to raise; do not spuriously retry.
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.config.max_tokens = None
        llm.generate_response.return_value = {"tool_calls": [{"name": "save_memories", "arguments": "truncat"}]}
        assert recover_extraction_via_tools(llm, "sys", "user") == []
        assert llm.generate_response.call_count == 1

    def test_token_raise_retry_is_capped(self):
        # 4x a large configured budget would be very expensive; the retry is
        # capped at an absolute ceiling (8192) instead.
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.config.max_tokens = 4000  # 4x = 16000, above the cap
        llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "save_memories", "arguments": '{"memory": [{"text": "cut of'}]},
            {"tool_calls": [{"name": "save_memories", "arguments": {"memory": [{"text": "Recovered"}]}}]},
        ]
        result = recover_extraction_via_tools(llm, "sys", "user")
        assert result == [{"text": "Recovered"}]
        retry_kwargs = llm.generate_response.call_args_list[1].kwargs
        assert retry_kwargs["max_tokens"] == 8192

    def test_no_token_raise_retry_when_budget_already_at_cap(self):
        # If the configured budget is already at/above the cap there is no
        # meaningful raise to attempt; skip the retry rather than re-spend the
        # same budget.
        llm = MagicMock()
        llm.supports_tool_calls = True
        llm.config.max_tokens = 8192
        llm.generate_response.return_value = {
            "tool_calls": [{"name": "save_memories", "arguments": '{"memory": [{"text": "cut of'}]
        }
        assert recover_extraction_via_tools(llm, "sys", "user") == []
        assert llm.generate_response.call_count == 1
