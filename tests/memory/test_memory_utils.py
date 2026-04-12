import pytest
from mem0.memory.utils import parse_vision_messages, remove_spaces_from_entities, sanitize_relationship_for_cypher


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


class TestParseVisionMessages:
    """
    Covers parse_vision_messages, specifically that list-typed or image_url-typed
    content does NOT crash when llm=None (vision disabled).
    """

    def test_plain_text_passthrough(self):
        """Regular text messages are always passed through unchanged."""
        messages = [{"role": "user", "content": "Hello"}]
        assert parse_vision_messages(messages) == messages

    def test_system_message_passthrough(self):
        """System messages are always passed through regardless of content type."""
        messages = [{"role": "system", "content": "You are helpful."}]
        assert parse_vision_messages(messages) == messages

    def test_list_content_no_llm_does_not_crash(self):
        """
        Regression test for: list-typed content with llm=None raises
        AttributeError: 'NoneType' object has no attribute 'generate_response'.
        When vision is disabled (llm=None) the message must be passed through as-is.
        """
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "What do you see?"}],
            }
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == messages

    def test_image_url_dict_content_no_llm_does_not_crash(self):
        """
        Regression test: single image_url dict content with llm=None must not crash.
        """
        messages = [
            {
                "role": "user",
                "content": {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            }
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == messages

    def test_mixed_messages_no_llm(self):
        """Mix of text and list-content messages — all passed through when llm=None."""
        messages = [
            {"role": "user", "content": "plain text"},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://x.com/a.jpg"}}]},
            {"role": "assistant", "content": "response"},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == messages

    def test_list_content_with_llm_calls_llm(self):
        """When llm is provided, get_image_description should be called."""
        class FakeLLM:
            def generate_response(self, messages):
                return "A described image"

        messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://x.com/img.jpg"}}]}]
        result = parse_vision_messages(messages, llm=FakeLLM())
        assert result == [{"role": "user", "content": "A described image"}]
