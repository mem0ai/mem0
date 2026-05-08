"""Unit tests for the ``_resolve_linked_memory_ids`` helper that translates
LLM-asserted links into persistable UUIDs.

These tests cover only the pure resolution helper (no LLM / vector store /
embeddings involved), which is sufficient to verify the bug fix: the raw
links produced by the extraction prompt are now preserved rather than
silently dropped.
"""

import pytest

from mem0.memory.main import _resolve_linked_memory_ids


UUID_A = "a1b2c3d4-0000-0000-0000-111111111111"
UUID_B = "b2c3d4e5-0000-0000-0000-222222222222"
UUID_C = "c3d4e5f6-0000-0000-0000-333333333333"


@pytest.fixture
def mapping():
    """Typical mapping produced at Phase 1 of ``_add_to_vector_store``."""
    return {"0": UUID_A, "1": UUID_B, "2": UUID_C}


class TestResolveLinkedMemoryIds:
    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_sequential_indices_resolve_to_uuids(self, mapping):
        """LLM outputs ``"0","1"`` — must translate to the mapped UUIDs."""
        result = _resolve_linked_memory_ids(["0", "1"], mapping)
        assert result == [UUID_A, UUID_B]

    def test_uuids_passed_through_when_known(self, mapping):
        """LLM outputs UUIDs directly — pass through if they match existing."""
        result = _resolve_linked_memory_ids([UUID_B, UUID_C], mapping)
        assert result == [UUID_B, UUID_C]

    def test_mixed_indices_and_uuids(self, mapping):
        result = _resolve_linked_memory_ids(["0", UUID_C], mapping)
        assert result == [UUID_A, UUID_C]

    # ------------------------------------------------------------------
    # Safety / robustness
    # ------------------------------------------------------------------

    def test_none_input_returns_empty_list(self, mapping):
        assert _resolve_linked_memory_ids(None, mapping) == []

    def test_empty_list_returns_empty(self, mapping):
        assert _resolve_linked_memory_ids([], mapping) == []

    def test_non_list_returns_empty(self, mapping):
        assert _resolve_linked_memory_ids("0", mapping) == []
        assert _resolve_linked_memory_ids({"0": UUID_A}, mapping) == []

    def test_unknown_index_is_dropped(self, mapping):
        """An index the LLM invented (not in mapping) must not leak into payload."""
        result = _resolve_linked_memory_ids(["0", "99"], mapping)
        assert result == [UUID_A]

    def test_unknown_uuid_is_dropped(self, mapping):
        """Hallucinated UUIDs that don't match any existing memory are dropped."""
        bogus = "deadbeef-0000-0000-0000-000000000000"
        result = _resolve_linked_memory_ids([bogus, "1"], mapping)
        assert result == [UUID_B]

    def test_non_string_items_are_skipped(self, mapping):
        result = _resolve_linked_memory_ids(["0", 42, None, UUID_C], mapping)
        assert result == [UUID_A, UUID_C]

    def test_whitespace_is_trimmed(self, mapping):
        result = _resolve_linked_memory_ids(["  0  ", "\t1"], mapping)
        assert result == [UUID_A, UUID_B]

    def test_empty_mapping_falls_back_to_uuid_only(self):
        """When no existing memories were shown, only raw UUIDs cannot be
        validated — they are safely dropped (no false positives)."""
        result = _resolve_linked_memory_ids([UUID_A, "0"], {})
        assert result == []

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def test_duplicates_are_deduplicated_preserving_order(self, mapping):
        result = _resolve_linked_memory_ids(
            ["0", UUID_A, "0", "1", UUID_B], mapping
        )
        assert result == [UUID_A, UUID_B]

    def test_duplicate_via_index_and_uuid_deduplicated(self, mapping):
        """Same memory referenced via index AND UUID must appear once."""
        result = _resolve_linked_memory_ids(["0", UUID_A], mapping)
        assert result == [UUID_A]
