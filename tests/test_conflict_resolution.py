"""
TDD tests for LLM-driven conflict resolution in the v2 ADD-only pipeline.

Issue: mem0ai/mem0#4904
Branch: feat/conflict-resolution-fix

When a new fact contradicts an existing memory (e.g., a name change), the LLM
signals the contradiction via a `contradicts` field in its output. The pipeline
routes that memory to UPDATE instead of ADD, replacing the outdated fact rather
than accumulating both.
"""
import hashlib
import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory


@pytest.fixture(autouse=True)
def set_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")


@pytest.fixture
def memory_with_mocks():
    """
    Builds a Memory instance with all external dependencies mocked out.

    Why mock at the factory level? Memory.__init__ calls EmbedderFactory.create(),
    VectorStoreFactory.create(), etc. Patching those factories lets us control
    what self.embedding_model, self.vector_store, and self.llm are — without
    needing a real OpenAI key, a running Qdrant instance, or a network connection.

    Why patch mem0.memory.main.SQLiteManager (not mem0.memory.storage.SQLiteManager)?
    main.py does `from mem0.memory.storage import SQLiteManager`, which creates a
    local binding in main's namespace at import time. Patching the source module
    doesn't intercept the already-bound local name. Patching the usage site does.
    """
    with (
        patch("mem0.utils.factory.EmbedderFactory.create") as mock_embedder_create,
        patch("mem0.utils.factory.VectorStoreFactory.create") as mock_vs_create,
        patch("mem0.utils.factory.LlmFactory.create") as mock_llm_create,
        patch("mem0.memory.main.SQLiteManager") as mock_sqlite,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder = MagicMock()
        mock_vs = MagicMock()
        mock_llm = MagicMock()
        mock_db = MagicMock()

        mock_embedder_create.return_value = mock_embedder
        mock_vs_create.return_value = mock_vs
        mock_llm_create.return_value = mock_llm
        mock_sqlite.return_value = mock_db
        mock_db.get_last_messages.return_value = []

        config = MemoryConfig()
        memory = Memory(config)

        yield memory, mock_vs, mock_embedder, mock_llm, mock_db


def _make_existing_memory(memory_id, text, user_id, score=0.92):
    """Helper: build a mock vector store result with realistic fields."""
    mem = Mock()
    mem.id = memory_id
    mem.payload = {
        "data": text,
        "user_id": user_id,
        "hash": hashlib.md5(text.encode()).hexdigest(),
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    mem.score = score
    return mem


def _contradiction_llm_response(new_text, contradicts_id="0"):
    """
    Build a mock LLM response where the extracted memory signals a contradiction.

    The `contradicts` field uses the integer ID from the Existing Memories list
    (not a UUID). The pipeline resolves it via uuid_mapping.
    """
    return json.dumps(
        {"memory": [{"id": "0", "text": new_text, "contradicts": contradicts_id}]}
    )


def _additive_llm_response(new_text, linked_ids=None):
    """Build a mock LLM response for a normal, non-contradictory ADD."""
    mem = {"id": "0", "text": new_text}
    if linked_ids:
        mem["linked_memory_ids"] = linked_ids
    return json.dumps({"memory": [mem]})


# ---------------------------------------------------------------------------
# Cycle 1 — adding a contradictory fact returns UPDATE, not ADD
# ---------------------------------------------------------------------------


def test_contradictory_name_returns_update_event(memory_with_mocks):
    """
    Cycle 1: adding "my name is Bob" when "User's name is Alice" already exists
    should produce an UPDATE event, not a second ADD.

    How it works: Phase 1 retrieves the existing Alice memory and builds
    uuid_mapping = {"0": "existing-alice-id"}. The LLM sees Alice in its context
    and outputs `contradicts: "0"`. Phase 2.5 resolves that to the real UUID and
    routes to _update_memory instead of ADD.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("existing-alice-id", "User's name is Alice", "test_user")
    # Phase 1 search returns existing memory → uuid_mapping["0"] = "existing-alice-id"
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    mock_llm.generate_response.return_value = _contradiction_llm_response("User's name is Bob")
    mock_vs.get.return_value = existing  # needed by _update_memory

    result = memory.add("my name is Bob", user_id="test_user")

    events = [r["event"] for r in result["results"]]
    assert "UPDATE" in events, (
        f"Expected contradiction to produce UPDATE event, got: {events}. "
        "The LLM signals contradictions via the `contradicts` field."
    )
    assert "ADD" not in events, (
        f"Expected no ADD event for a contradictory fact, got: {events}. "
        "A second ADD stores both names, degrading memory quality."
    )


def test_contradictory_name_update_targets_correct_memory(memory_with_mocks):
    """
    Cycle 1 (companion): the UPDATE result must carry the existing memory's ID.
    This ensures the old record is replaced in the vector store, not a ghost
    record created alongside it.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("existing-alice-id", "User's name is Alice", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    mock_llm.generate_response.return_value = _contradiction_llm_response("User's name is Bob")
    mock_vs.get.return_value = existing

    result = memory.add("my name is Bob", user_id="test_user")

    update_results = [r for r in result["results"] if r.get("event") == "UPDATE"]
    assert update_results, "Expected at least one UPDATE result"
    assert update_results[0]["id"] == "existing-alice-id", (
        f"UPDATE must reference the existing memory ID, got: {update_results[0]['id']}"
    )


# ---------------------------------------------------------------------------
# Cycle 2 — after conflict resolution the vector store has ONE record, not two
# ---------------------------------------------------------------------------


def test_conflict_calls_update_not_insert(memory_with_mocks):
    """
    Cycle 2: resolving a contradiction must call vector_store.update() on the
    existing ID and must NOT call vector_store.insert() — which would create a
    second, duplicate entry.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("existing-alice-id", "User's name is Alice", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    mock_llm.generate_response.return_value = _contradiction_llm_response("User's name is Bob")
    mock_vs.get.return_value = existing

    memory.add("my name is Bob", user_id="test_user")

    mock_vs.update.assert_called_once()
    assert mock_vs.update.call_args.kwargs.get("vector_id") == "existing-alice-id", (
        f"update() must target the existing memory ID, got: {mock_vs.update.call_args}"
    )
    mock_vs.insert.assert_not_called()


def test_get_all_returns_one_result_after_conflict(memory_with_mocks):
    """
    Cycle 2 (end-to-end): after a contradiction-resolution add, get_all() returns
    exactly 1 memory containing the newer value, not the old one.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("existing-alice-id", "User's name is Alice", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    mock_llm.generate_response.return_value = _contradiction_llm_response("User's name is Bob")
    mock_vs.get.return_value = existing

    memory.add("my name is Bob", user_id="test_user")

    updated_record = _make_existing_memory("existing-alice-id", "User's name is Bob", "test_user")
    mock_vs.list.return_value = [updated_record]

    all_mem = memory.get_all(filters={"user_id": "test_user"})

    assert len(all_mem["results"]) == 1, (
        f"Expected 1 memory after conflict resolution, got {len(all_mem['results'])}"
    )
    assert "Bob" in all_mem["results"][0]["memory"]
    assert "Alice" not in all_mem["results"][0]["memory"]


# ---------------------------------------------------------------------------
# Cycle 3 — conflict resolution writes a correct UPDATE history entry
# ---------------------------------------------------------------------------


def test_conflict_writes_update_history(memory_with_mocks):
    """
    Cycle 3: when a contradiction is resolved, db.add_history() must be called
    with event="UPDATE", the old memory text, and the new memory text.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("existing-alice-id", "User's name is Alice", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    mock_llm.generate_response.return_value = _contradiction_llm_response("User's name is Bob")
    mock_vs.get.return_value = existing

    memory.add("my name is Bob", user_id="test_user")

    mock_db.add_history.assert_called_once()
    call_args = mock_db.add_history.call_args

    # Positional args: (memory_id, old_memory, new_memory, event, ...)
    assert call_args.args[0] == "existing-alice-id"
    assert call_args.args[1] == "User's name is Alice", (
        f"old_memory must be the original text, got: {call_args.args[1]}"
    )
    assert call_args.args[2] == "User's name is Bob", (
        f"new_memory must be the replacement text, got: {call_args.args[2]}"
    )
    assert call_args.args[3] == "UPDATE"


# ---------------------------------------------------------------------------
# Cycle 4 — no `contradicts` field in LLM output → ADD (no false positives)
# ---------------------------------------------------------------------------


def test_no_contradicts_field_produces_add(memory_with_mocks):
    """
    Cycle 4a: when the LLM does NOT include a `contradicts` field, the memory
    is stored as a new ADD regardless of how similar it is to existing memories.

    This is the core guard against false positives. Similarity alone no longer
    triggers UPDATE — only an explicit LLM judgment does.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    existing = _make_existing_memory("coffee-id", "User loves coffee", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.2, 0.9, 0.1]]
    # LLM correctly identifies this as additive, not a contradiction
    mock_llm.generate_response.return_value = _additive_llm_response(
        "User loves tea", linked_ids=["<uuid-of-coffee-memory>"]
    )

    result = memory.add("I also really love tea", user_id="test_user")

    events = [r["event"] for r in result["results"]]
    assert events == ["ADD"], (
        f"Additive preference should produce ADD, got: {events}. "
        "Both coffee and tea preferences can be true simultaneously."
    )
    mock_vs.insert.assert_called_once()
    mock_vs.update.assert_not_called()


def test_no_existing_memories_produces_add(memory_with_mocks):
    """
    Cycle 4b: when there are no existing memories at all (empty vector store),
    adding any fact must produce an ADD event. This is the baseline case.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    mock_vs.search.return_value = []
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.5, 0.5, 0.0]]
    mock_llm.generate_response.return_value = _additive_llm_response("User's name is Alice")

    result = memory.add("my name is Alice", user_id="new_user")

    events = [r["event"] for r in result["results"]]
    assert events == ["ADD"]
    mock_vs.insert.assert_called_once()
    mock_vs.update.assert_not_called()


def test_contradicts_id_not_in_mapping_falls_back_to_add(memory_with_mocks):
    """
    Cycle 4c: if the LLM hallucinates a `contradicts` ID that doesn't correspond
    to any existing memory in uuid_mapping, the pipeline logs a warning and falls
    back to ADD rather than crashing or silently dropping the memory.
    """
    memory, mock_vs, mock_embedder, mock_llm, mock_db = memory_with_mocks

    # Phase 1 returns one existing memory → uuid_mapping = {"0": "some-id"}
    existing = _make_existing_memory("some-id", "User's name is Alice", "test_user")
    mock_vs.search.return_value = [existing]
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.embed_batch.return_value = [[0.9, 0.1, 0.0]]
    # LLM outputs contradicts: "99" — an ID that doesn't exist in uuid_mapping
    mock_llm.generate_response.return_value = _contradiction_llm_response(
        "User's name is Bob", contradicts_id="99"
    )

    result = memory.add("my name is Bob", user_id="test_user")

    # Should fall back to ADD, not crash
    events = [r["event"] for r in result["results"]]
    assert "ADD" in events, (
        f"Hallucinated contradicts ID should fall back to ADD, got: {events}"
    )
    mock_vs.update.assert_not_called()
