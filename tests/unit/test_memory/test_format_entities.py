"""Tests for mem0.memory.utils.format_entities."""

from mem0.memory.utils import format_entities


class TestFormatEntities:
    def test_empty_list(self):
        assert format_entities([]) == ""

    def test_none(self):
        assert format_entities(None) == ""

    def test_normal_entities(self):
        entities = [{"source": "Alice", "relationship": "works_at", "destination": "Acme"}]
        result = format_entities(entities)
        assert result == "Alice -- works_at -- Acme"

    def test_missing_destination_key(self):
        """Missing keys should not crash with KeyError."""
        entities = [{"source": "Alice", "relationship": "knows"}]
        result = format_entities(entities)
        assert result == "Alice -- knows -- "

    def test_missing_all_keys(self):
        entities = [{}]
        result = format_entities(entities)
        assert result == ""

    def test_non_dict_entity_skipped(self):
        entities = [{"source": "A", "relationship": "r", "destination": "B"}, "bad_string"]
        result = format_entities(entities)
        assert result == "A -- r -- B"

    def test_multiple_entities(self):
        entities = [
            {"source": "A", "relationship": "r1", "destination": "B"},
            {"source": "C", "relationship": "r2", "destination": "D"},
        ]
        result = format_entities(entities)
        assert "A -- r1 -- B" in result
        assert "C -- r2 -- D" in result
