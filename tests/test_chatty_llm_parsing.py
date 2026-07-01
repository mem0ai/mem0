"""Tests for chatty LLM JSON parsing robustness.

Validates that extract_json and the full fallback chain correctly handle
responses from local LLMs (LM Studio, Ollama) that wrap JSON in
conversational text, markdown code blocks, or both.
"""

import json

import pytest

from mem0.memory.utils import extract_json, remove_code_blocks, salvage_memory_objects

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


class TestSalvageTruncatedMemories:
    """salvage_memory_objects: recover the complete memory objects from a
    response truncated mid-stream (the model hit max_tokens), dropping only the
    half-written tail object."""

    def test_recovers_complete_objects_drops_cut_off_tail(self):
        # Memories 1-4 finished; memory 5 was cut off mid-write.
        truncated = (
            '{"memory": ['
            '{"id": "0", "text": "User likes hiking in the Laurel Highlands"}, '
            '{"id": "1", "text": "User was promoted to Senior Engineer"}, '
            '{"id": "2", "text": "User has a wife named Elena"}, '
            '{"id": "3", "text": "User celebrated at Osteria Francescana"}, '
            '{"id": "4", "text": "User has a dog nam'
        )
        memories, was_truncated = salvage_memory_objects(truncated)
        assert was_truncated is True
        assert len(memories) == 4  # the cut-off 5th is dropped
        assert [m["id"] for m in memories] == ["0", "1", "2", "3"]
        assert all("nam" not in m["text"] or m["text"].endswith("nam") is False for m in memories)
        assert "dog nam" not in memories[-1]["text"]

    def test_clean_array_reports_not_truncated(self):
        # json.loads failed on the whole blob (trailing junk), but the array closed.
        text = '{"memory": [{"id": "0", "text": "Name is Alex"}]} <<trailing garbage'
        memories, was_truncated = salvage_memory_objects(text)
        assert was_truncated is False
        assert len(memories) == 1
        assert memories[0]["text"] == "Name is Alex"

    def test_no_memory_array_returns_empty_not_truncated(self):
        # Content-hijack (prose, no JSON) is not a truncation case.
        memories, was_truncated = salvage_memory_objects("I need to ask you a few questions first.")
        assert memories == []
        assert was_truncated is False

    def test_empty_input(self):
        assert salvage_memory_objects("") == ([], False)

    def test_non_string_input_degrades_instead_of_raising(self):
        # salvage runs inside the parse-failure except handler; a provider
        # returning a non-string (dict, None, list) must degrade to "nothing
        # salvaged", never raise out of the error handler.
        assert salvage_memory_objects({"unexpected": "dict"}) == ([], False)
        assert salvage_memory_objects(None) == ([], False)
        assert salvage_memory_objects(["a", "list"]) == ([], False)

    def test_truncated_right_after_an_object_before_array_close(self):
        # Cut after object 1's '}' but before ']' -> object 1 complete, still truncated.
        text = '{"memory": [{"id": "0", "text": "Name is Alex"}, '
        memories, was_truncated = salvage_memory_objects(text)
        assert len(memories) == 1
        assert was_truncated is True

    def test_recovers_single_quoted_python_repr_dict(self):
        # Some models emit a Python-repr dict ({'memory': [...]}) instead of JSON.
        # json.loads / extract_json both fail on it upstream, so it lands here. The
        # double-quoted-only peeler would match nothing and SILENTLY drop every
        # fact - the adjacent silent-drop this function exists to prevent.
        text = "{'memory': [{'id': '0', 'text': \"User's dog is named Biscuit\"}, {'id': '1', 'text': 'Lives in Pittsburgh'}]}"
        memories, was_truncated = salvage_memory_objects(text)
        assert was_truncated is False  # array closed cleanly
        assert [m["id"] for m in memories] == ["0", "1"]
        assert memories[0]["text"] == "User's dog is named Biscuit"  # apostrophe inside survives

    def test_single_quoted_but_truncated_is_not_dropped_silently(self, caplog):
        # Single-quoted AND cut off mid-stream: literal_eval cannot recover (no
        # closing ']'), so nothing is salvaged - but it must be logged, not dropped
        # silently. Asserts the loud-warning floor for the unrecoverable case.
        import logging

        text = "{'memory': [{'id': '0', 'text': 'Lives in Pitt"
        with caplog.at_level(logging.WARNING):
            memories, _ = salvage_memory_objects(text)
        assert memories == []
        assert any("not dropping silently" in r.message for r in caplog.records)

    def test_bracket_inside_string_does_not_break_recovery(self):
        # An UNBALANCED ']' inside a memory's text must not be mistaken for the
        # array close. The text holds a lone ']' with no matching '[', so a naive
        # non-quote-aware scanner would stop at it and mis-slice; only the
        # quote-aware matcher walks past it and recovers the object.
        text = "{'memory': [{'id': '0', 'text': 'rated 9] stars'}]}"
        memories, was_truncated = salvage_memory_objects(text)
        assert was_truncated is False
        assert len(memories) == 1
        assert memories[0]["text"] == "rated 9] stars"
