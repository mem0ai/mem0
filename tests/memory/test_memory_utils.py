import pytest
from unittest.mock import Mock

from mem0.memory.utils import (
    normalize_extracted_memories,
    parse_messages,
    parse_vision_messages,
    remove_spaces_from_entities,
    sanitize_relationship_for_cypher,
)


class TestParseMessages:
    def test_skips_message_without_content_key(self):
        # Reproduces #5067: a FunctionCalling assistant message carries
        # `tool_calls` but no `content` key -> used to raise KeyError.
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "search"}}]},
            {"role": "assistant", "content": "done"},
        ]
        result = parse_messages(messages)
        assert result == "user: hi\nassistant: done\n"

    def test_skips_explicit_none_content(self):
        messages = [{"role": "assistant", "content": None}, {"role": "user", "content": "ok"}]
        assert parse_messages(messages) == "user: ok\n"

    def test_plain_roles_pass_through(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]
        assert parse_messages(messages) == "system: sys\nuser: u\nassistant: a\n"


class TestParseVisionMessages:
    def test_skips_message_without_content_key(self):
        # Reproduces #5067 for the vision parser path.
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "search"}}]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "hi"}

    def test_multimodal_list_without_llm_extracts_text(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is this?"

    def test_image_dict_without_llm_is_skipped(self):
        messages = [
            {"role": "user", "content": {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}}},
            {"role": "user", "content": "hello"},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_multimodal_with_llm_calls_generate_response(self):
        mock_llm = Mock()
        mock_llm.generate_response.return_value = "A photo of a cat"
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this"},
                {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=mock_llm, vision_details="auto")
        assert result[0]["content"] == "A photo of a cat"
        mock_llm.generate_response.assert_called_once()

    def test_image_only_list_without_llm_is_skipped(self):
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == []

    def test_plain_text_messages_pass_through(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == messages

    def test_malformed_image_dict_raises_value_error(self):
        # A malformed image part (missing the nested url) used to raise an
        # uncaught KeyError that aborted add(); it should raise a clear ValueError.
        mock_llm = Mock()
        messages = [{"role": "user", "content": {"type": "image_url", "image_url": {}}}]
        with pytest.raises(ValueError, match=r"missing image_url\.url"):
            parse_vision_messages(messages, llm=mock_llm)
        mock_llm.generate_response.assert_not_called()

    def test_none_image_url_raises_value_error(self):
        # image_url present but None (or any non-dict) must also raise the clear
        # ValueError, not an AttributeError from calling .get() on None.
        mock_llm = Mock()
        messages = [{"role": "user", "content": {"type": "image_url", "image_url": None}}]
        with pytest.raises(ValueError, match=r"missing image_url\.url"):
            parse_vision_messages(messages, llm=mock_llm)
        mock_llm.generate_response.assert_not_called()


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


class TestNormalizeExtractedMemories:
    def test_passthrough_wellformed_text_dict_preserves_keys(self):
        items = [{"text": "User likes coffee", "attributed_to": "user", "linked_memory_ids": ["a"]}]
        out = normalize_extracted_memories(items)
        assert out == [{"text": "User likes coffee", "attributed_to": "user", "linked_memory_ids": ["a"]}]

    def test_plain_string_is_wrapped(self):
        # Without normalization, downstream m.get("text") raises AttributeError on a str.
        out = normalize_extracted_memories(["User likes coffee"])
        assert out == [{"text": "User likes coffee"}]

    def test_fact_key_dict_is_mapped_to_text(self):
        out = normalize_extracted_memories([{"fact": "User likes coffee"}])
        assert out == [{"fact": "User likes coffee", "text": "User likes coffee"}]

    def test_key_as_fact_single_key_dict(self):
        # grok-style reasoning models emit {factText: <value>}; the key IS the fact.
        out = normalize_extracted_memories([{"User likes coffee": "noise"}])
        assert out == [{"User likes coffee": "noise", "text": "User likes coffee"}]

    def test_empty_and_unrecognized_shapes_are_dropped(self):
        out = normalize_extracted_memories(["", {}, {"a": 1, "b": 2}, 42, None])
        assert out == []

    def test_mixed_batch(self):
        items = ["plain", {"text": "kept"}, {"User is tired": "x"}]
        out = normalize_extracted_memories(items)
        assert [m["text"] for m in out] == ["plain", "kept", "User is tired"]
