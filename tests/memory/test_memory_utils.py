import pytest
from mem0.memory.utils import (
    normalize_extracted_memories,
    normalize_facts,
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


class TestNormalizeFacts:
    """Tolerates the malformed shapes real LLMs emit for the FACT_RETRIEVAL prompt."""

    def test_plain_strings_pass_through(self):
        assert normalize_facts(["one", "two"]) == ["one", "two"]

    def test_well_formed_dicts(self):
        assert normalize_facts([{"fact": "Name is Thales"}, {"text": "Lives in Vancouver"}]) == [
            "Name is Thales",
            "Lives in Vancouver",
        ]

    def test_malformed_key_as_fact(self):
        """Observed with grok-on-OpenAI-compatible: fact text is the dict key."""
        raw = [{"User's name is Thales.": "nova-check"}]
        assert normalize_facts(raw) == ["User's name is Thales."]

    def test_single_value_string_when_key_is_garbage(self):
        raw = [{"_id": "abc-123"}]  # key is structurally meaningful, value is the fact? edge case
        # We prefer the key when it's a non-empty string; this test pins that choice.
        assert normalize_facts(raw) == ["_id"]

    def test_empty_and_none_inputs(self):
        assert normalize_facts(None) == []
        assert normalize_facts([]) == []

    def test_skip_unparseable(self, caplog):
        # Multi-key dict with no fact/text falls through to the warning branch.
        raw = [{"a": 1, "b": 2}]
        out = normalize_facts(raw)
        assert out == []


class TestNormalizeExtractedMemories:
    """Same shape tolerance as normalize_facts, but preserves dict structure
    so downstream code can access .text / .event / .attributed_to."""

    def test_well_formed_dicts_pass_through(self):
        raw = [
            {"text": "Name is Thales", "event": "ADD"},
            {"text": "Lives in Vancouver", "event": "ADD", "attributed_to": "user"},
        ]
        assert normalize_extracted_memories(raw) == raw

    def test_fact_key_promoted_to_text(self):
        raw = [{"fact": "Name is Thales", "event": "ADD"}]
        out = normalize_extracted_memories(raw)
        assert out[0]["text"] == "Name is Thales"
        assert out[0]["event"] == "ADD"

    def test_malformed_key_as_fact_synthesizes_dict(self):
        """The bug this patch fixes: single-key {factText: anything} from grok-style LLMs."""
        raw = [{"User's name is Thales.": "nova-check"}]
        out = normalize_extracted_memories(raw)
        assert len(out) == 1
        assert out[0] == {"text": "User's name is Thales.", "event": "ADD"}

    def test_plain_string_wrapped(self):
        out = normalize_extracted_memories(["bare string fact"])
        assert out == [{"text": "bare string fact", "event": "ADD"}]

    def test_non_dict_non_string_skipped(self):
        assert normalize_extracted_memories([42, None, ["nested"]]) == []

    def test_empty_and_none_inputs(self):
        assert normalize_extracted_memories(None) == []
        assert normalize_extracted_memories([]) == []

    def test_multi_key_unparseable_skipped(self):
        raw = [{"a": 1, "b": "value"}]
        assert normalize_extracted_memories(raw) == []
