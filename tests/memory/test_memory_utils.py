import pytest
from mem0.memory.utils import (
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


class TestParseVisionMessagesNoLLM:
    """
    When enable_vision=False (the default), Memory.add() calls
    parse_vision_messages(messages) without an LLM. Messages whose
    content is a list or an image_url dict must pass through unchanged
    instead of crashing on llm.generate_response().
    """

    def test_list_content_passes_through_without_llm(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        ]
        out = parse_vision_messages(messages)
        assert out == messages

    def test_image_url_dict_content_passes_through_without_llm(self):
        messages = [
            {
                "role": "user",
                "content": {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/cat.png"},
                },
            }
        ]
        out = parse_vision_messages(messages)
        assert out == messages

    def test_system_message_preserved(self):
        messages = [
            {"role": "system", "content": "you are a bot"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        ]
        out = parse_vision_messages(messages)
        assert out == messages

    def test_plain_text_message_unchanged(self):
        messages = [{"role": "user", "content": "plain text"}]
        out = parse_vision_messages(messages)
        assert out == messages
