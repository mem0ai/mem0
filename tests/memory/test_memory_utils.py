import pytest
from mem0.memory.utils import (
    parse_messages,
    parse_vision_messages,
    remove_spaces_from_entities,
    sanitize_relationship_for_cypher,
)


class TestRemoveSpacesFromEntities:
    """
    Covers behavior used by Neo4j, Memgraph (sanitize_relationship=True),
    Kuzu, and Neptune (sanitize_relationship=False). All backends delegate here.
    """

    @pytest.mark.parametrize(
        "sanitize",
        [True, False],
        ids=["cypher_sanitized", "plain"],
    )
    def test_filters_empty_and_incomplete_dicts(self, sanitize):
        mixed = [
            {},
            {"source": "a"},
            {"source": "a", "relationship": "r"},
            {"source": "x", "relationship": "rel", "destination": "y"},
        ]
        out = remove_spaces_from_entities(mixed, sanitize_relationship=sanitize)
        assert len(out) == 1
        assert out[0]["source"] == "x"
        assert out[0]["destination"] == "y"

    @pytest.mark.parametrize("sanitize", [True, False])
    def test_all_empty_returns_empty(self, sanitize):
        assert remove_spaces_from_entities([{}, {}, {}], sanitize_relationship=sanitize) == []

    def test_skips_non_dict_entries(self):
        assert remove_spaces_from_entities([None, "not-a-dict", 123, {"source": "a", "relationship": "r", "destination": "b"}]) == [
            {"source": "a", "relationship": "r", "destination": "b"}
        ]

    def test_sanitize_true_relationship_uses_sanitizer(self):
        """Neo4j / Memgraph path: special characters mapped via sanitize_relationship_for_cypher."""
        entities = [{"source": "A", "relationship": "x/y", "destination": "B"}]
        out = remove_spaces_from_entities(entities, sanitize_relationship=True)
        assert out[0]["relationship"] == sanitize_relationship_for_cypher("x/y".lower().replace(" ", "_"))

    def test_sanitize_false_relationship_plain_only(self):
        """Kuzu / Neptune path: only lowercase and spaces to underscores."""
        entities = [{"source": "A", "relationship": "Works At", "destination": "B Co"}]
        out = remove_spaces_from_entities(entities, sanitize_relationship=False)
        assert out[0]["relationship"] == "works_at"
        assert out[0]["source"] == "a"
        assert out[0]["destination"] == "b_co"

    def test_sanitize_true_vs_false_slash_in_relationship(self):
        """Slash is rewritten when sanitizing (Cypher path); kept as-is for plain path."""
        base = {"source": "s", "relationship": "a/b", "destination": "d"}
        t = remove_spaces_from_entities([dict(base)], sanitize_relationship=True)[0]["relationship"]
        f = remove_spaces_from_entities([dict(base)], sanitize_relationship=False)[0]["relationship"]
        assert t == sanitize_relationship_for_cypher("a/b")
        assert f == "a/b"


class TestParseMessagesSafeAccess:
    """Test that parse_messages handles messages with missing keys (issue #5067).

    When Dify's FunctionCalling agent calls Mem0 as a tool, it may send assistant
    messages with tool_calls but no content key, or tool-role messages. These should
    be gracefully skipped rather than raising a KeyError.
    """

    def test_assistant_message_without_content_is_skipped(self):
        """Assistant message with tool_calls but no content should not raise KeyError."""
        messages = [
            {"role": "user", "content": "Remember I like tennis"},
            {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "add_memory"}}]},
        ]
        result = parse_messages(messages)
        assert "user: Remember I like tennis" in result
        assert "assistant" not in result

    def test_tool_role_message_is_skipped(self):
        """Tool-role messages (from function calling) should be skipped."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "tool", "tool_call_id": "call_1", "content": "Memory stored"},
        ]
        result = parse_messages(messages)
        assert "user: Hello" in result
        assert "Memory stored" not in result

    def test_message_without_role_key_is_skipped(self):
        """Messages missing the role key entirely should be skipped."""
        messages = [
            {"content": "orphan message"},
            {"role": "user", "content": "valid message"},
        ]
        result = parse_messages(messages)
        assert "orphan" not in result
        assert "valid message" in result

    def test_message_without_content_key_is_skipped(self):
        """Messages missing the content key should be skipped."""
        messages = [
            {"role": "user"},
            {"role": "assistant", "content": "valid"},
        ]
        result = parse_messages(messages)
        assert "valid" in result

    def test_empty_messages_list(self):
        result = parse_messages([])
        assert result == ""

    def test_normal_messages_still_work(self):
        """Ensure normal message parsing is unaffected by the fix."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = parse_messages(messages)
        assert "system: You are a helpful assistant." in result
        assert "user: Hello" in result
        assert "assistant: Hi there!" in result

    def test_dify_function_calling_conversation(self):
        """Simulate a full Dify FunctionCalling conversation."""
        messages = [
            {"role": "system", "content": "You have access to mem0 tools."},
            {"role": "user", "content": "Remember I like tennis"},
            {"role": "assistant", "tool_calls": [
                {"id": "call_abc", "function": {"name": "add_memory", "arguments": "{...}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_abc", "content": "{\"results\": []}"},
            {"role": "assistant", "content": "Done!"},
        ]
        result = parse_messages(messages)
        assert "system: You have access to mem0 tools." in result
        assert "user: Remember I like tennis" in result
        assert "assistant: Done!" in result
        # tool_calls-only assistant message should be skipped
        assert "tool_calls" not in result


class TestParseVisionMessagesSafeAccess:
    """Test that parse_vision_messages handles messages with missing keys (issue #5067)."""

    def test_assistant_message_without_content_is_skipped(self):
        """Assistant tool_calls message without content should be skipped, not KeyError."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "tool_calls": [{"id": "call_1"}]},
        ]
        result = parse_vision_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_tool_role_message_is_skipped(self):
        """Tool messages without content should be skipped."""
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "tool", "tool_call_id": "call_1"},
        ]
        result = parse_vision_messages(messages)
        assert len(result) == 1

    def test_system_message_without_content_passthrough(self):
        """System messages are passed through directly even if content is missing."""
        messages = [{"role": "system", "content": "You are helpful."}]
        result = parse_vision_messages(messages)
        assert len(result) == 1

    def test_message_without_role_is_skipped(self):
        messages = [
            {"content": "orphan"},
            {"role": "user", "content": "valid"},
        ]
        result = parse_vision_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_normal_messages_still_work(self):
        """Ensure normal vision message parsing is unaffected."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = parse_vision_messages(messages)
        assert len(result) == 3
