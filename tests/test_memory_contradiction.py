"""Tests for the memory contradiction detection and superseding feature.

This module tests the opt-in contradiction detection pipeline (Phase 1.5)
added to the V3 memory ingestion pipeline. It verifies that:

1. Contradicted memories are soft-deleted (is_superseded=True) and excluded
   from search/get_all results.
2. Non-contradictory facts are not falsely superseded.
3. The feature is fully opt-in — disabled by default with zero impact on
   existing behavior.
4. LLM failures in detection are non-fatal and do not break the add() pipeline.
"""

import json
from unittest.mock import MagicMock, patch

from mem0.configs.base import MemoryConfig


class MockVectorMemory:
    """Mock memory object for testing vector store payloads."""

    def __init__(self, memory_id: str, payload: dict, score: float = 0.8):
        self.id = memory_id
        self.payload = payload
        self.score = score


# ---------------------------------------------------------------------------
# Helper: build a fully-mocked Memory instance with contradiction detection ON
# ---------------------------------------------------------------------------


def _make_memory(
    mock_sqlite,
    mock_llm_factory,
    mock_vector_factory,
    mock_embedder_factory,
    enable_contradiction_detection=True,
):
    """Create a Memory instance with all dependencies mocked.

    By default, contradiction detection is enabled so we can test the new
    Phase 1.5 logic. Pass enable_contradiction_detection=False to test the
    backward-compatible (unchanged) code paths.
    """
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    mock_embedder.config = MagicMock(embedding_dims=3)
    mock_embedder_factory.return_value = mock_embedder

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []
    mock_vector_store.insert.return_value = None
    mock_vector_store.update.return_value = None
    mock_vector_store.get.return_value = None
    mock_vector_store.keyword_search.return_value = None

    # VectorStoreFactory.create is called twice: once for main store, once for telemetry
    telemetry_vector_store = MagicMock()
    mock_vector_factory.side_effect = [mock_vector_store, telemetry_vector_store]

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = json.dumps({"memory": []})
    mock_llm_factory.return_value = mock_llm

    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig(enable_contradiction_detection=enable_contradiction_detection)
    memory = MemoryClass(config)

    return memory, mock_vector_store, mock_llm, mock_embedder


# ===========================================================================
# Test 1: Core scenario — "coffee → tea" supersedes old memory
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_coffee_to_tea_supersedes_old_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Scenario: User previously said 'I like coffee', then says 'I don't like
    coffee anymore, I like tea'. The coffee memory should be soft-deleted
    (is_superseded=True) via the Phase 1.5 contradiction detection.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,
    )

    # Simulate existing "coffee" memory returned by Phase 1 vector search
    coffee_memory = MockVectorMemory(
        "coffee-uuid-111",
        {
            "data": "User likes drinking coffee",
            "hash": "abc123",
            "created_at": "2025-01-01T00:00:00+00:00",
        },
        score=0.9,
    )
    mock_vs.search.return_value = [coffee_memory]

    # First LLM call: contradiction detection → identifies coffee memory as superseded
    # Second LLM call: additive extraction → extracts the new tea memory
    mock_llm.generate_response.side_effect = [
        json.dumps({"superseded_ids": ["0"]}),
        json.dumps({"memory": [{"text": "User likes drinking tea instead of coffee"}]}),
    ]

    memory.add(
        "I don't like coffee anymore, I like tea now.",
        user_id="test_user",
        infer=True,
    )

    # Assert: vector_store.update was called to stamp is_superseded=True on the coffee memory
    update_calls = mock_vs.update.call_args_list
    assert len(update_calls) >= 1, "Expected at least one update call to supersede the coffee memory"

    # Find the supersede call (the one with is_superseded=True)
    supersede_call = None
    for call in update_calls:
        call_payload = call.kwargs.get("payload") or (call.args[2] if len(call.args) > 2 else None)
        if call_payload and call_payload.get("is_superseded") is True:
            supersede_call = call
            break

    assert supersede_call is not None, "Expected a supersede update call with is_superseded=True"

    # Verify the supersede targeted the correct memory ID
    supersede_vector_id = supersede_call.kwargs.get("vector_id") or supersede_call.args[0]
    assert supersede_vector_id == "coffee-uuid-111"


# ===========================================================================
# Test 2: Non-contradictory add preserves both memories
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_non_contradictory_add_preserves_both_memories(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    Adding unrelated facts ('I like coffee' and 'I have a dog') should NOT
    trigger any superseding — both memories must remain active.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,
    )

    # Existing coffee memory
    coffee_memory = MockVectorMemory(
        "coffee-uuid-111",
        {"data": "User likes drinking coffee", "hash": "abc123"},
        score=0.5,
    )
    mock_vs.search.return_value = [coffee_memory]

    # LLM returns no contradictions, then extracts new memory
    mock_llm.generate_response.side_effect = [
        json.dumps({"superseded_ids": []}),  # No contradictions found
        json.dumps({"memory": [{"text": "User has a dog named Buddy"}]}),
    ]

    memory.add("I have a dog named Buddy.", user_id="test_user", infer=True)

    # Assert: no update call should have is_superseded=True
    for call in mock_vs.update.call_args_list:
        call_payload = call.kwargs.get("payload") or (call.args[2] if len(call.args) > 2 else None)
        if call_payload:
            assert call_payload.get("is_superseded") is not True, "Non-contradictory memory was incorrectly superseded"


# ===========================================================================
# Test 3: Detection is skipped when config flag is disabled (default)
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_contradiction_detection_skipped_when_disabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    With enable_contradiction_detection=False (the default), no extra LLM call
    should be made for contradiction detection. The LLM should only be called
    once for extraction.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=False,  # Default behavior
    )

    # Existing memory present
    existing_memory = MockVectorMemory(
        "mem-uuid-111",
        {"data": "User likes coffee", "hash": "abc123"},
        score=0.9,
    )
    mock_vs.search.return_value = [existing_memory]

    # LLM should only be called once (for extraction, not for contradiction detection)
    mock_llm.generate_response.return_value = json.dumps({"memory": []})

    memory.add("I don't like coffee anymore.", user_id="test_user", infer=True)

    # LLM should have been called exactly once (extraction only)
    assert mock_llm.generate_response.call_count == 1, (
        f"Expected 1 LLM call (extraction only), got {mock_llm.generate_response.call_count}"
    )


# ===========================================================================
# Test 4: Detection is skipped when no existing memories are found
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_contradiction_detection_skipped_on_empty_existing(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    When Phase 1 returns no existing memories, the contradiction detection
    LLM call should be skipped entirely (no point asking about contradictions
    if there's nothing to contradict).
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,
    )

    # No existing memories
    mock_vs.search.return_value = []

    mock_llm.generate_response.return_value = json.dumps({"memory": [{"text": "User likes tea"}]})

    memory.add("I like tea.", user_id="test_user", infer=True)

    # LLM should have been called only once (extraction), not twice
    assert mock_llm.generate_response.call_count == 1, (
        f"Expected 1 LLM call (extraction only), got {mock_llm.generate_response.call_count}"
    )


# ===========================================================================
# Test 5: SUPERSEDE event is recorded in history
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.main.SQLiteManager")
def test_supersede_stamped_in_history(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    When a memory is superseded, a SUPERSEDE event should be recorded in the
    SQLite history table with the correct memory_id and event type.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,
    )

    coffee_memory = MockVectorMemory(
        "coffee-uuid-222",
        {
            "data": "User likes coffee",
            "hash": "def456",
            "created_at": "2025-01-01T00:00:00+00:00",
        },
        score=0.9,
    )
    mock_vs.search.return_value = [coffee_memory]

    mock_llm.generate_response.side_effect = [
        json.dumps({"superseded_ids": ["0"]}),
        json.dumps({"memory": [{"text": "User likes tea"}]}),
    ]

    memory.add("I like tea now, not coffee.", user_id="test_user", infer=True)

    # Find the SUPERSEDE history call
    history_calls = memory.db.add_history.call_args_list
    supersede_calls = [
        c for c in history_calls if (c.args[3] if len(c.args) > 3 else c.kwargs.get("event")) == "SUPERSEDE"
    ]

    assert len(supersede_calls) >= 1, "Expected at least one SUPERSEDE history entry"

    # Verify the correct memory ID was recorded
    supersede_call = supersede_calls[0]
    recorded_memory_id = supersede_call.args[0] if supersede_call.args else supersede_call.kwargs.get("memory_id")
    assert recorded_memory_id == "coffee-uuid-222"


# ===========================================================================
# Test 6: Search excludes superseded memories
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_excludes_superseded_memories(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Memories with is_superseded=True in their payload should be excluded from
    search results by the _search_vector_store filtering logic.
    """
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.config = MagicMock(embedding_dims=3)
    mock_embedder_factory.return_value = mock_embedder

    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    mem_instance = MemoryClass(config)

    # Simulate search returning both a superseded and a normal memory
    superseded_mem = MockVectorMemory(
        "superseded-mem-1",
        {"data": "User likes coffee", "is_superseded": True, "hash": "aaa"},
        score=0.9,
    )
    active_mem = MockVectorMemory(
        "active-mem-2",
        {"data": "User likes tea", "hash": "bbb"},
        score=0.85,
    )
    mock_vector_store.search.return_value = [superseded_mem, active_mem]
    mock_vector_store.keyword_search.return_value = None

    result = mem_instance._search_vector_store("drink preference", {"user_id": "test"}, 10)

    # Only the active memory should appear in results
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"
    assert result[0]["id"] == "active-mem-2"
    assert result[0]["memory"] == "User likes tea"


# ===========================================================================
# Test 7: get_all excludes superseded memories
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_get_all_excludes_superseded_memories(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    Memories with is_superseded=True should be excluded from get_all results.
    The is_superseded flag appears in the payload metadata.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    mem_instance = MemoryClass(config)

    superseded_mem = MockVectorMemory(
        "superseded-mem-1",
        {"data": "User likes coffee", "is_superseded": True, "hash": "aaa"},
    )
    active_mem = MockVectorMemory(
        "active-mem-2",
        {"data": "User likes tea", "hash": "bbb"},
    )
    mock_vector_store.list.return_value = [superseded_mem, active_mem]

    result = mem_instance._get_all_from_vector_store({"user_id": "test"}, 100)

    # Only the active memory should appear
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"
    assert result[0]["memory"] == "User likes tea"


# ===========================================================================
# Test 8: LLM failure in detection does not break add()
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_llm_failure_in_detection_does_not_break_add(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    If the LLM raises an exception during contradiction detection (Phase 1.5),
    the overall add() operation should still succeed — detection failures are
    non-fatal by design.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,
    )

    # Existing memory
    existing_memory = MockVectorMemory(
        "mem-uuid-333",
        {"data": "User likes coffee", "hash": "abc123"},
        score=0.9,
    )
    mock_vs.search.return_value = [existing_memory]

    # First call (contradiction detection) raises an exception,
    # second call (extraction) succeeds
    mock_llm.generate_response.side_effect = [
        RuntimeError("LLM API timeout"),
        json.dumps({"memory": [{"text": "User mentioned something about drinks"}]}),
    ]

    # This should NOT raise — detection failure is swallowed
    result = memory.add("I like tea.", user_id="test_user", infer=True)

    assert "results" in result
    # The new memory should still be inserted despite detection failure
    assert mock_vs.insert.called


# ===========================================================================
# Test 9: Original pipeline unbroken with infer=False
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_original_pipeline_unbroken_infer_false(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    With infer=False, the add() pipeline takes the non-LLM direct-insert path.
    Contradiction detection should have zero involvement regardless of config.
    """
    memory, mock_vs, mock_llm, _ = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=True,  # Even when enabled...
    )

    memory.add("Direct memory text.", user_id="test_user", infer=False)

    # LLM should never be called for infer=False
    mock_llm.generate_response.assert_not_called()

    # Insert should still happen
    assert mock_vs.insert.called


# ===========================================================================
# Test 10: Original pipeline unbroken with infer=True but flag off
# ===========================================================================


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_original_pipeline_unbroken_infer_true_no_flag(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    With infer=True but enable_contradiction_detection=False (the default),
    the pipeline should behave exactly as before — one LLM call for extraction,
    embed_batch for Phase 3, and insert for Phase 6.
    """
    memory, mock_vs, mock_llm, mock_embedder = _make_memory(
        mock_sqlite,
        mock_llm_factory,
        mock_vector_factory,
        mock_embedder_factory,
        enable_contradiction_detection=False,
    )

    # Existing memory in the store
    existing_memory = MockVectorMemory(
        "existing-mem-id",
        {
            "data": "User likes Python",
            "hash": "abc123",
            "created_at": "2025-01-01T00:00:00+00:00",
        },
    )
    mock_vs.search.return_value = [existing_memory]

    # Single extraction call
    mock_llm.generate_response.return_value = json.dumps({"memory": [{"text": "The user enjoys coding"}]})
    mock_embedder.embed_batch.return_value = [[0.4, 0.5, 0.6]]

    memory.add("I enjoy coding", user_id="test_user", infer=True)

    # V3 pipeline: embed once (Phase 1 query), LLM once (extraction), embed_batch once (Phase 3)
    assert mock_embedder.embed.call_count == 1
    assert mock_llm.generate_response.call_count == 1
    assert mock_embedder.embed_batch.call_count == 1
    assert mock_vs.insert.called
