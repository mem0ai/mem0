import pytest
from unittest.mock import Mock

from mem0.memory.utils import (
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


class TestCapTextForEmbedding:
    """Regression coverage for issue #5148 — protect existing-memory retrieval
    from embedding-provider token-limit crashes on long conversations.

    The helper truncates from the front (keeps the tail) so the most-recent
    content drives retrieval, matching the intent of the retrieval step in
    Memory._add_to_vector_store Phase 1.
    """

    def test_short_text_passes_through(self):
        from mem0.memory.utils import cap_text_for_embedding

        text = "hello world"
        assert cap_text_for_embedding(text) == text

    def test_long_text_is_truncated_to_budget(self):
        from mem0.memory.utils import cap_text_for_embedding

        max_chars = 100
        long_text = "x" * (max_chars * 3)
        out = cap_text_for_embedding(long_text, max_chars=max_chars)
        assert len(out) == max_chars

    def test_long_text_keeps_the_tail(self):
        """Recency matters most for retrieval — the most recent content
        (which the user just said) should be preserved when truncating."""
        from mem0.memory.utils import cap_text_for_embedding

        head = "OLD" * 100
        tail = "RECENT-CONTENT-MARKER"
        long_text = head + tail
        out = cap_text_for_embedding(long_text, max_chars=len(tail) + 5)
        # The recent marker must survive truncation
        assert tail in out
        # And the old content must be gone (or at least mostly gone)
        assert out.endswith(tail)

    def test_default_budget_under_8192_token_limit(self):
        """The default budget must stay safely under common 8192-token
        embedding limits even with worst-case ~3 chars/token packing."""
        from mem0.memory.utils import DEFAULT_RETRIEVAL_EMBED_CHAR_BUDGET

        # Worst-case token estimate (3 chars/token); must stay under 8192.
        worst_case_tokens = DEFAULT_RETRIEVAL_EMBED_CHAR_BUDGET / 3
        assert worst_case_tokens < 8192

    def test_non_string_input_returned_unchanged(self):
        """Defensive: callers may accidentally pass non-string input."""
        from mem0.memory.utils import cap_text_for_embedding

        assert cap_text_for_embedding(None) is None
        assert cap_text_for_embedding(12345) == 12345
