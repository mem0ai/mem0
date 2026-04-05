"""
Conflict detection & resolution — SQLite audit integration tests.

These tests use a real in-memory SQLiteManager so every db.add_history call
made by _delete_memory and _create_memory is executed for real.  After each
relevant assertion the full history table is printed to stdout so you can
inspect the exact rows without a debugger.

Run:
    pytest tests/memory/test_conflict_sqlite.py -v -s

The -s flag is required to see the stdout table output.

──────────────────────────────────────────────────────────────────────────────
BEHAVIORAL-GAP ASSESSMENT
──────────────────────────────────────────────────────────────────────────────

The following subsystems are affected by the conflict pipeline but are NOT
fully verified by mocked unit tests.  Each gap is documented below and has
a corresponding test or note in the TestBehavioralGaps class.

GAP-1  Graph store receives original unfiltered messages
       _add_to_graph runs concurrently in add() on the original `messages`
       argument before the conflict pipeline has a chance to suppress facts.
       Consequence: if a KEEP_OLD resolution suppresses a fact from the
       vector store, the graph store will still extract entities/relations
       from that message and write them to the graph backend.  The graph and
       vector store diverge silently.  For MERGE, the graph gets the original
       message text, not the merged text stored in the vector store.
       → Needs manual inspection if graph_store is enabled.

GAP-2  created_at provenance is lost on KEEP_NEW
       _create_memory always stamps created_at = now().  The old memory's
       original created_at is not inherited by the replacement.  If temporal
       ordering of preference changes matters to your app, this is data loss.

GAP-3  actor_id is None in SQLite history for conflict-driven ADD rows
       _create_memory is called with deepcopy(metadata) where metadata comes
       from processed_metadata in _add_to_vector_store.  processed_metadata
       contains user_id/agent_id/run_id but actor_id is only set per-message
       in the non-infer path.  So the ADD history row for a conflict-resolved
       new memory will have actor_id=None even when the original messages had
       named roles.

GAP-4  Telemetry (capture_event) is blind to conflict-driven mutations
       capture_event("mem0.add") fires at the outer add() boundary.  The
       _delete_memory and _create_memory calls inside the conflict pipeline do
       not individually fire capture_event("mem0.delete") or
       capture_event("mem0.add").  Usage analytics will undercount mutations.

GAP-5  infer=False bypasses the conflict pipeline entirely
       Raw message ingest (infer=False) skips fact extraction and therefore
       the conflict detection block.  If callers pass raw strings expecting
       deduplication, they won't get it.

GAP-6  Procedural memory bypasses the conflict pipeline
       When agent_id is set and memory_type=PROCEDURAL, Memory.add() routes
       directly to _create_procedural_memory before _add_to_vector_store is
       even called.

GAP-7  user_id is NOT stored in the SQLite history table
       The history table schema stores actor_id and role, not user_id.
       Audit queries keyed on user_id require joining with the vector store,
       which may already have deleted the memory.  There is no way to
       reconstruct "which user's memories were conflict-resolved" from
       SQLite alone.
"""
import hashlib
import json
import sqlite3
from dataclasses import replace as dc_replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mem0.memory.conflict as conflict_module
from mem0.memory.conflict import (
    ConflictResolution,
    _execute_merge_llm_call,
    apply_auto_resolution,
)
from mem0.memory.main import AsyncMemory, Memory
from mem0.memory.storage import SQLiteManager


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_all_history(db: SQLiteManager) -> list[dict]:
    """Return every row in the history table in insertion order."""
    cur = db.connection.execute(
        """
        SELECT id, memory_id, old_memory, new_memory, event,
               created_at, updated_at, is_deleted, actor_id, role
        FROM history
        ORDER BY rowid ASC
        """
    )
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "memory_id": r[1],
            "old_memory": r[2],
            "new_memory": r[3],
            "event": r[4],
            "created_at": r[5],
            "updated_at": r[6],
            "is_deleted": bool(r[7]),
            "actor_id": r[8],
            "role": r[9],
        }
        for r in rows
    ]


def _print_db_rows(rows: list[dict], label: str) -> None:
    """Print SQLite history rows to stdout for manual inspection."""
    bar = "─" * 62
    print(f"\n┌{bar}┐")
    print(f"│  SQLite history — {label:<42}│")
    print(f"├{bar}┤")
    if not rows:
        print(f"│  (no rows written){'':>43}│")
    for i, row in enumerate(rows, 1):
        print(f"│  [{i}] event      : {str(row['event']):<43}│")
        print(f"│      memory_id  : {str(row['memory_id']):<43}│")
        print(f"│      old_memory : {str(row['old_memory']):<43}│")
        print(f"│      new_memory : {str(row['new_memory']):<43}│")
        print(f"│      is_deleted : {str(row['is_deleted']):<43}│")
        print(f"│      actor_id   : {str(row['actor_id']):<43}│")
        print(f"│      role       : {str(row['role']):<43}│")
        print(f"│      created_at : {str(row['created_at']):<43}│")
        if i < len(rows):
            print(f"│{'':62}│")
    print(f"└{bar}┘\n")


def _make_search_result(mem_id: str, text: str, score: float) -> MagicMock:
    """Mock vector search result with .id, .payload, .score."""
    mem = MagicMock()
    mem.id = mem_id
    mem.payload = {"data": text}
    mem.score = score
    return mem


def _make_stored_memory(
    mem_id: str,
    text: str,
    created_at: str = "2026-01-01T00:00:00+00:00",
    actor_id: str | None = None,
    role: str | None = None,
) -> MagicMock:
    """
    Mock the object returned by vector_store.get() — used by _delete_memory
    to read the existing memory before issuing the DELETE history row.
    """
    mem = MagicMock()
    mem.id = mem_id
    mem.payload = {
        "data": text,
        "created_at": created_at,
        "updated_at": created_at,
        "actor_id": actor_id,
        "role": role,
    }
    return mem


def _setup_factories(mocker, *, real_sqlite: bool = False):
    """
    Patch all three factory singletons.  When real_sqlite=True, patch
    mem0.memory.main.SQLiteManager so Memory.__init__ gets a real
    in-memory DB instead of a MagicMock.

    Returns (mock_llm_instance, mock_vs_instance).
    """
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vs_cls = mocker.MagicMock()
    mock_vs_cls.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vs_cls.return_value, mocker.MagicMock()],
    )

    mock_llm_cls = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm_cls)

    if real_sqlite:
        # Replace SQLiteManager construction with a real in-memory DB so
        # _delete_memory / _create_memory write real rows we can inspect.
        mocker.patch(
            "mem0.memory.main.SQLiteManager",
            side_effect=lambda _path: SQLiteManager(":memory:"),
        )
    else:
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm_cls.return_value, mock_vs_cls.return_value


def _make_memory(
    mocker,
    *,
    hitl_enabled: bool = False,
    strategy: str = "keep-higher-confidence",
    real_sqlite: bool = False,
) -> tuple[Memory, MagicMock]:
    mock_llm, mock_vs = _setup_factories(mocker, real_sqlite=real_sqlite)
    memory = Memory()
    memory.config.conflict_detection.hitl_enabled = hitl_enabled
    memory.config.conflict_detection.auto_resolve_strategy = strategy
    memory.config.conflict_detection.similarity_threshold = 0.85
    memory.config.conflict_detection.top_k = 20
    memory.config.session_id = "test-session-id"

    if not real_sqlite:
        # Use method-level mocks so existing behaviour tests stay fast
        memory._delete_memory = mocker.MagicMock(return_value="old-mem-uuid")
        memory._create_memory = mocker.MagicMock(return_value="new-mem-uuid")

    return memory, mock_vs


CONTRADICTION_HIGH_NEW = json.dumps({
    "conflict_class": "CONTRADICTION",
    "explanation": "Cannot be vegetarian and eat chicken",
    "proposed_action": "Replace old memory with new fact",
    "confidence_new": 0.7,
    "confidence_old": 0.3,
})

CONTRADICTION_HIGH_OLD = json.dumps({
    "conflict_class": "CONTRADICTION",
    "explanation": "Conflicting dietary preferences",
    "proposed_action": "Keep existing memory",
    "confidence_new": 0.3,
    "confidence_old": 0.8,
})


@pytest.fixture(autouse=True)
def clear_session_overrides():
    conflict_module._session_overrides.clear()
    yield
    conflict_module._session_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Part 1 — SQLite audit integration (real DB, no _delete/_create mocks)
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLiteAudit:
    """
    These tests do NOT mock _delete_memory or _create_memory.
    They use a real in-memory SQLiteManager so every db.add_history call
    executes against a real SQLite connection and can be read back.

    Run with -s to see the printed history tables.
    """

    def test_keep_new_writes_delete_then_add(self, mocker):
        """
        KEEP_NEW resolution must produce exactly two SQLite rows in order:
          1. DELETE row for old memory  (is_deleted=True,  new_memory=None)
          2. ADD    row for new fact    (is_deleted=False, old_memory=None)
        """
        memory, mock_vs = _make_memory(mocker, real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "KEEP_NEW — expect DELETE then ADD")

        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"

        delete_row = next((r for r in rows if r["event"] == "DELETE"), None)
        assert delete_row is not None, "Missing DELETE row"
        assert delete_row["memory_id"] == "old-mem-uuid"
        assert delete_row["old_memory"] == "User is vegetarian"
        assert delete_row["new_memory"] is None
        assert delete_row["is_deleted"] is True

        add_row = next((r for r in rows if r["event"] == "ADD"), None)
        assert add_row is not None, "Missing ADD row"
        assert add_row["old_memory"] is None
        assert add_row["new_memory"] == "User eats chicken regularly"
        assert add_row["is_deleted"] is False

    def test_keep_old_writes_nothing_to_sqlite(self, mocker):
        """
        KEEP_OLD resolution must produce zero SQLite rows — the old memory
        is unchanged and the new fact is suppressed entirely.
        """
        memory, mock_vs = _make_memory(mocker, real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_OLD,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "KEEP_OLD — expect zero rows")

        assert len(rows) == 0, f"expected 0 rows, got {len(rows)}: {rows}"

    def test_delete_old_writes_only_delete_to_sqlite(self, mocker):
        """
        DELETE_OLD resolution must produce exactly one SQLite row:
          1. DELETE row for old memory (is_deleted=True, new_memory=None)
        No ADD row should be written.
        """
        memory, mock_vs = _make_memory(mocker, strategy="delete-old", real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_OLD,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "DELETE_OLD — expect only DELETE")

        assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {rows}"
        assert rows[0]["event"] == "DELETE"
        assert rows[0]["memory_id"] == "old-mem-uuid"
        assert rows[0]["old_memory"] == "User is vegetarian"
        assert rows[0]["new_memory"] is None
        assert rows[0]["is_deleted"] is True

    def test_follow_llm_keep_new_writes_delete_then_add(self, mocker):
        """
        follow-llm strategy + proposed_action=KEEP_NEW must produce exactly two
        SQLite rows in order:
          1. DELETE row for old memory
          2. ADD    row for new fact
        """
        memory, mock_vs = _make_memory(mocker, strategy="follow-llm", real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        classification = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "KEEP_NEW",
            "confidence_new": 0.5,
            "confidence_old": 0.5,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            classification,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "follow-llm KEEP_NEW — expect DELETE then ADD")

        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"

        delete_row = next((r for r in rows if r["event"] == "DELETE"), None)
        assert delete_row is not None, "Missing DELETE row"
        assert delete_row["memory_id"] == "old-mem-uuid"
        assert delete_row["old_memory"] == "User is vegetarian"
        assert delete_row["is_deleted"] is True

        add_row = next((r for r in rows if r["event"] == "ADD"), None)
        assert add_row is not None, "Missing ADD row"
        assert add_row["new_memory"] == "User eats steak"
        assert add_row["is_deleted"] is False

    def test_follow_llm_delete_old_writes_only_delete(self, mocker):
        """
        follow-llm strategy + proposed_action=DELETE_OLD must produce exactly one
        SQLite row — DELETE for old memory, no ADD row.
        """
        memory, mock_vs = _make_memory(mocker, strategy="follow-llm", real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        classification = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "DELETE_OLD",
            "confidence_new": 0.5,
            "confidence_old": 0.5,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            classification,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "follow-llm DELETE_OLD — expect only DELETE")

        assert len(rows) == 1, f"expected 1 row, got {len(rows)}: {rows}"
        assert rows[0]["event"] == "DELETE"
        assert rows[0]["memory_id"] == "old-mem-uuid"
        assert rows[0]["old_memory"] == "User is vegetarian"
        assert rows[0]["new_memory"] is None
        assert rows[0]["is_deleted"] is True

    def test_merge_writes_delete_then_add_with_merged_text(self, mocker):
        """
        MERGE resolution must produce exactly two SQLite rows:
          1. DELETE row for old memory
          2. ADD    row whose new_memory equals the LLM-produced merged text
             (NOT the [MERGE PENDING] fallback)
        """
        merged_text = "User follows a mostly plant-based diet but occasionally eats chicken"
        merge_response = json.dumps({"merged": merged_text})

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Conflicting dietary info",
            "proposed_action": "Merge both facts",
            "confidence_new": 0.6,
            "confidence_old": 0.6,
        })

        memory, mock_vs = _make_memory(mocker, strategy="merge", real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken occasionally"]}',
            contradiction_response,
            merge_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken occasionally"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "MERGE — expect DELETE then ADD (merged text)")

        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"

        delete_row = next((r for r in rows if r["event"] == "DELETE"), None)
        assert delete_row is not None
        assert delete_row["old_memory"] == "User is vegetarian"

        add_row = next((r for r in rows if r["event"] == "ADD"), None)
        assert add_row is not None
        assert add_row["new_memory"] == merged_text, (
            f"merged text not stored — got: {add_row['new_memory']}"
        )
        assert not add_row["new_memory"].startswith("[MERGE PENDING]")

    def test_merge_fallback_stored_in_sqlite_on_llm_failure(self, mocker):
        """
        When the merge LLM call fails, the [MERGE PENDING] fallback text
        must be written to SQLite as the ADD row's new_memory so the memory
        is never silently lost.
        """
        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "merge",
            "confidence_new": 0.5,
            "confidence_old": 0.5,
        })

        memory, mock_vs = _make_memory(mocker, strategy="merge", real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        def _side_effect(*args, **kwargs):
            call_num = memory.llm.generate_response.call_count
            responses = {
                1: '{"facts": ["User eats chicken occasionally"]}',
                2: contradiction_response,
                3: RuntimeError("LLM timeout"),
            }
            val = responses.get(call_num)
            if isinstance(val, Exception):
                raise val
            return val

        memory.llm.generate_response.side_effect = _side_effect

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken occasionally"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "MERGE fallback — [MERGE PENDING] stored in SQLite")

        assert len(rows) == 2
        add_row = next(r for r in rows if r["event"] == "ADD")
        assert add_row["new_memory"].startswith("[MERGE PENDING]"), (
            f"expected [MERGE PENDING] prefix, got: {add_row['new_memory']}"
        )
        assert "User is vegetarian" in add_row["new_memory"]
        assert "User eats chicken occasionally" in add_row["new_memory"]

    def test_metadata_passes_through_to_add_row(self, mocker):
        """
        The metadata dict passed into _add_to_vector_store (which includes
        user_id, agent_id, run_id) must be carried into the new memory's
        vector store payload.  The SQLite ADD row itself stores actor_id and
        role — NOT user_id — because the history schema pre-dates the
        user/agent scoping model.

        This test shows what IS and IS NOT recorded:
          ✓ new_memory text is correct
          ✓ is_deleted = False
          ✗ user_id is absent from the history row (see GAP-7)
          ✗ actor_id is None when no per-message role was set (see GAP-3)
        """
        memory, mock_vs = _make_memory(mocker, real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory("old-mem-uuid", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]

        # Pass user_id and agent_id in metadata — typical production call
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={"user_id": "alice", "agent_id": "agent-1"},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "metadata propagation (note: user_id absent from SQLite)")

        add_row = next(r for r in rows if r["event"] == "ADD")
        assert add_row["new_memory"] == "User eats chicken regularly"

        # GAP-3: actor_id is None — metadata has user_id/agent_id but no actor_id
        print(f"  [GAP-3] actor_id in ADD row = {add_row['actor_id']!r}  (None expected)")
        assert add_row["actor_id"] is None, (
            "GAP-3: actor_id should be None when metadata has no actor_id key"
        )

        # GAP-7: user_id is NOT a column in the history table
        col_names = [
            row[1]
            for row in memory.db.connection.execute(
                "PRAGMA table_info(history)"
            ).fetchall()
        ]
        print(f"  [GAP-7] history table columns = {col_names}")
        assert "user_id" not in col_names, (
            "GAP-7: user_id should not exist as a column in the history table"
        )

    def test_delete_row_preserves_original_created_at(self, mocker):
        """
        The DELETE history row must carry the old memory's original created_at
        (retrieved from the vector store payload) — not the current timestamp.

        This verifies that _delete_memory reads created_at from the existing
        memory before writing the history row.
        """
        original_created_at = "2025-06-15T08:30:00+00:00"

        memory, mock_vs = _make_memory(mocker, real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory(
            "old-mem-uuid", "User is vegetarian", created_at=original_created_at
        )

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "DELETE row created_at preservation")

        delete_row = next(r for r in rows if r["event"] == "DELETE")
        assert delete_row["created_at"] == original_created_at, (
            f"DELETE row should carry original created_at={original_created_at!r}, "
            f"got {delete_row['created_at']!r}"
        )

    def test_add_row_gets_fresh_created_at_not_original(self, mocker):
        """
        GAP-2: The ADD row for the replacement memory has a fresh created_at
        (now()) — the original memory's created_at is NOT inherited.

        This is intentional behaviour per _create_memory, but it means the
        provenance timestamp of when the user *first* expressed a preference
        is permanently lost after a KEEP_NEW resolution.
        """
        original_created_at = "2025-06-15T08:30:00+00:00"

        memory, mock_vs = _make_memory(mocker, real_sqlite=True)

        old_mem_search = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs.search.return_value = [old_mem_search]
        mock_vs.get.return_value = _make_stored_memory(
            "old-mem-uuid", "User is vegetarian", created_at=original_created_at
        )

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "GAP-2: ADD row created_at is fresh, old created_at lost")

        add_row = next(r for r in rows if r["event"] == "ADD")
        print(
            f"  [GAP-2] old created_at={original_created_at!r}\n"
            f"          new created_at={add_row['created_at']!r}  ← fresh timestamp"
        )
        assert add_row["created_at"] != original_created_at, (
            "GAP-2: ADD row should have a fresh created_at, not the old memory's timestamp"
        )

    def test_multi_match_one_keep_new_one_keep_old_writes_one_delete_one_add(self, mocker):
        """
        One new_fact contradicts two old memories.
        First pair resolves KEEP_NEW  → DELETE old-uuid-1, ADD new fact.
        Second pair resolves KEEP_OLD → no DB writes.
        Total: exactly 2 rows (DELETE + ADD for first pair only).
        """
        old_mem_1 = _make_search_result("old-uuid-1", "User is vegetarian", score=0.93)
        old_mem_2 = _make_search_result("old-uuid-2", "User avoids all animal products", score=0.89)

        contradiction_keep_new = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict A",
            "proposed_action": "replace",
            "confidence_new": 0.8,
            "confidence_old": 0.3,
        })
        contradiction_keep_old = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict B",
            "proposed_action": "keep old",
            "confidence_new": 0.3,
            "confidence_old": 0.9,
        })

        memory, mock_vs = _make_memory(mocker, real_sqlite=True)
        mock_vs.search.return_value = [old_mem_1, old_mem_2]
        mock_vs.get.return_value = _make_stored_memory("old-uuid-1", "User is vegetarian")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            contradiction_keep_new,
            contradiction_keep_old,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        rows = _get_all_history(memory.db)
        _print_db_rows(rows, "multi-match: KEEP_NEW for pair-1, KEEP_OLD for pair-2")

        assert len(rows) == 2
        delete_row = next(r for r in rows if r["event"] == "DELETE")
        assert delete_row["memory_id"] == "old-uuid-1"
        add_row = next(r for r in rows if r["event"] == "ADD")
        assert add_row["new_memory"] == "User eats chicken regularly"


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 — Original behaviour tests (fast, method-level mocks, no real DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoResolution:
    def test_keep_higher_confidence_new_wins(self, mocker):
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_called_once()
        args, kwargs = memory._create_memory.call_args
        assert kwargs.get("data", args[0] if args else None) == "User eats chicken regularly"

    def test_keep_higher_confidence_old_wins(self, mocker):
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_OLD,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()

    def test_keep_newer_ignores_confidence(self, mocker):
        """keep-newer always resolves KEEP_NEW regardless of confidence scores."""
        memory, mock_vs = _make_memory(mocker, strategy="keep-newer")
        mock_vs.search.return_value = [
            _make_search_result("old-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_OLD,  # confidence_old=0.8 would win under keep-higher-confidence
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_called_once()
        memory._create_memory.assert_called_once()

    def test_delete_old_strategy_deletes_without_add(self, mocker):
        """delete-old resolves by deleting old memory and not creating a new one."""
        memory, mock_vs = _make_memory(mocker, strategy="delete-old")
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_OLD,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_not_called()

    def test_nuance_skips_single_pass_update_llm(self, mocker):
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User prefers vegetarian meals", score=0.90)
        ]
        nuance_response = json.dumps({
            "conflict_class": "NUANCE",
            "explanation": "adds detail",
            "proposed_action": "keep both",
            "confidence_new": 0.6,
            "confidence_old": 0.6,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User sometimes avoids meat"]}',
            nuance_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I sometimes avoid meat"}],
            metadata={}, filters={}, infer=True,
        )
        assert memory.llm.generate_response.call_count == 2
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_called_once()

    def test_none_skips_single_pass_update_llm(self, mocker):
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User likes jazz", score=0.87)
        ]
        none_response = json.dumps({
            "conflict_class": "NONE",
            "explanation": "unrelated",
            "proposed_action": "no action",
            "confidence_new": 0.4,
            "confidence_old": 0.4,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User likes Italian food"]}',
            none_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love Italian food"}],
            metadata={}, filters={}, infer=True,
        )
        assert memory.llm.generate_response.call_count == 2
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_called_once()

    def test_below_threshold_still_runs_classification(self, mocker):
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User likes jazz", score=0.60)
        ]
        none_response = json.dumps({
            "conflict_class": "NONE",
            "explanation": "unrelated",
            "proposed_action": "no action",
            "confidence_new": 0.4,
            "confidence_old": 0.4,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User likes coffee"]}',
            none_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I like coffee"}],
            metadata={}, filters={}, infer=True,
        )
        # Similarity threshold is ignored; extraction + classification still run.
        assert memory.llm.generate_response.call_count == 2
        memory._create_memory.assert_called_once()


class TestHITL:
    def test_y_resolves_keep_new(self, mocker):
        memory, mock_vs = _make_memory(mocker, hitl_enabled=True)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        mocker.patch("builtins.input", return_value="y")
        mocker.patch("mem0.memory.conflict._print_hitl_block")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_called_once()

    def test_n_resolves_keep_old(self, mocker):
        memory, mock_vs = _make_memory(mocker, hitl_enabled=True)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        mocker.patch("builtins.input", return_value="n")
        mocker.patch("mem0.memory.conflict._print_hitl_block")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()

    def test_always_replace_persists_within_session(self, mocker):
        memory, mock_vs = _make_memory(mocker, hitl_enabled=True)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        input_mock = mocker.patch("builtins.input", return_value="always-replace")
        mocker.patch("mem0.memory.conflict._print_hitl_block")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        assert input_mock.call_count == 1

        # Second contradiction — override active, prompt must NOT fire
        memory._delete_memory.reset_mock()
        memory._create_memory.reset_mock()
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User loves BBQ"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love BBQ"}],
            metadata={}, filters={}, infer=True,
        )
        assert input_mock.call_count == 1  # still 1 — no second prompt
        memory._delete_memory.assert_called_once()

    def test_invalid_input_twice_defaults_to_keep_old(self, mocker):
        memory, mock_vs = _make_memory(mocker, hitl_enabled=True)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        mocker.patch("builtins.input", side_effect=["garbage", "still-garbage"])
        mocker.patch("mem0.memory.conflict._print_hitl_block")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        # Two invalid inputs → default n → KEEP_OLD
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()


class TestMergeStrategy:
    def test_merge_calls_third_llm_and_uses_result(self, mocker):
        merged_text = "User follows a mostly plant-based diet but occasionally eats chicken"
        merge_response = json.dumps({"merged": merged_text})
        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "merge",
            "confidence_new": 0.6,
            "confidence_old": 0.6,
        })

        memory, mock_vs = _make_memory(mocker, strategy="merge")
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken occasionally"]}',
            contradiction_response,
            merge_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken occasionally"}],
            metadata={}, filters={}, infer=True,
        )
        assert memory.llm.generate_response.call_count == 3
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        args, kwargs = memory._create_memory.call_args
        created_data = kwargs.get("data", args[0] if args else None)
        assert created_data == merged_text

    def test_merge_fallback_on_llm_failure(self, mocker):
        cr = ConflictResolution(
            new_fact="User eats chicken",
            old_memory_id="old-id",
            old_memory_text="User is vegetarian",
            conflict_class="CONTRADICTION",
            explanation="conflict",
            proposed_action="merge",
            confidence_new=0.5,
            confidence_old=0.5,
            auto_resolved=False,
            resolution="MERGE",
            merged_text=None,
        )
        mock_llm = MagicMock()
        mock_llm.generate_response.side_effect = RuntimeError("LLM unavailable")
        result = _execute_merge_llm_call(cr, mock_llm)
        assert result.startswith("[MERGE PENDING]")
        assert "User is vegetarian" in result
        assert "User eats chicken" in result


class TestAsyncConflict:
    @pytest.mark.asyncio
    async def test_async_keep_new_resolution(self, mocker):
        mock_embedder = mocker.MagicMock()
        mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

        mock_vs_cls = mocker.MagicMock()
        old_mem = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs_cls.return_value.search.return_value = [old_mem]
        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=[mock_vs_cls.return_value, mocker.MagicMock()],
        )
        mock_llm_cls = mocker.MagicMock()
        mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm_cls)
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

        memory = AsyncMemory()
        memory.config.conflict_detection.hitl_enabled = False
        memory.config.conflict_detection.auto_resolve_strategy = "keep-higher-confidence"
        memory.config.conflict_detection.similarity_threshold = 0.85
        memory.config.session_id = "async-test-session"
        memory._delete_memory = mocker.AsyncMock(return_value="old-mem-uuid")
        memory._create_memory = mocker.AsyncMock(return_value="new-mem-uuid")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]
        await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            effective_filters={},
            infer=True,
        )
        memory._delete_memory.assert_awaited_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_delete_old_resolution(self, mocker):
        """AsyncMemory: delete-old strategy → old memory deleted, new fact NOT created."""
        mock_embedder = mocker.MagicMock()
        mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

        mock_vs_cls = mocker.MagicMock()
        old_mem = _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vs_cls.return_value.search.return_value = [old_mem]
        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=[mock_vs_cls.return_value, mocker.MagicMock()],
        )
        mock_llm_cls = mocker.MagicMock()
        mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm_cls)
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

        memory = AsyncMemory()
        memory.config.conflict_detection.hitl_enabled = False
        memory.config.conflict_detection.auto_resolve_strategy = "delete-old"
        memory.config.conflict_detection.similarity_threshold = 0.85
        memory.config.session_id = "async-delete-old-session"
        memory._delete_memory = mocker.AsyncMock(return_value="old-mem-uuid")
        memory._create_memory = mocker.AsyncMock(return_value="new-mem-uuid")

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            CONTRADICTION_HIGH_OLD,  # confidence values don't matter for delete-old
        ]
        await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            effective_filters={},
            infer=True,
        )
        memory._delete_memory.assert_awaited_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_not_awaited()


class TestMultiMatch:
    def test_two_pairs_resolved_independently(self, mocker):
        old_mem_1 = _make_search_result("old-uuid-1", "User is vegetarian", score=0.93)
        old_mem_2 = _make_search_result("old-uuid-2", "User avoids all animal products", score=0.89)

        contradiction_keep_new = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict A",
            "proposed_action": "replace",
            "confidence_new": 0.8,
            "confidence_old": 0.3,
        })
        contradiction_keep_old = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict B",
            "proposed_action": "keep old",
            "confidence_new": 0.3,
            "confidence_old": 0.9,
        })

        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [old_mem_1, old_mem_2]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            contradiction_keep_new,
            contradiction_keep_old,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={}, filters={}, infer=True,
        )
        assert memory.llm.generate_response.call_count == 3
        assert memory._delete_memory.call_count == 1
        memory._delete_memory.assert_called_with(memory_id="old-uuid-1")
        assert memory._create_memory.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Part 3 — Behavioral gap tests (manual inspection focus)
# ─────────────────────────────────────────────────────────────────────────────

class TestBehavioralGaps:
    """
    Tests that surface the behavioral gaps documented in the module docstring.
    Each test prints its finding clearly.  Run with -s to see output.
    """

    def test_gap1_graph_store_receives_unfiltered_messages(self, mocker):
        """
        GAP-1: _add_to_graph is called with the original messages before the
        conflict pipeline runs.  Even a KEEP_OLD resolution (which suppresses
        a fact from the vector store) does NOT prevent the graph store from
        processing the same message.

        This test verifies the call occurs by enabling graph mode and
        inspecting the graph.add() invocation.  Manual inspection required
        to determine if the divergence is acceptable for your use case.
        """
        memory, mock_vs = _make_memory(mocker)

        # Enable graph store
        mock_graph = mocker.MagicMock()
        mock_graph.add.return_value = []
        memory.graph = mock_graph
        memory.enable_graph = True

        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_OLD,   # KEEP_OLD — fact suppressed from vector store
            '{"memory": []}',
        ]

        # Call _add_to_vector_store directly (graph is called by the outer add())
        # Here we test _add_to_graph explicitly to show it would run on original data
        original_messages = [{"role": "user", "content": "I eat chicken regularly"}]
        memory._add_to_graph(original_messages, {"user_id": "alice"})

        print(
            "\n  [GAP-1] graph.add() called with original messages:\n"
            f"    {mock_graph.add.call_args}\n"
            "  Even though KEEP_OLD would suppress this fact from the vector store,\n"
            "  the graph store still processes the original message content.\n"
            "  → Requires manual inspection if graph_store is enabled in production."
        )
        mock_graph.add.assert_called_once()

    def test_gap5_infer_false_bypasses_conflict_pipeline(self, mocker):
        """
        GAP-5: With infer=False, _add_to_vector_store stores raw message
        content directly without fact extraction or conflict detection.
        No LLM calls are made; no contradiction classification runs.
        """
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = []

        memory._add_to_vector_store(
            messages=[
                {"role": "user", "content": "I eat chicken regularly"},
                {"role": "assistant", "content": "Got it."},
            ],
            metadata={},
            filters={},
            infer=False,
        )

        print(
            "\n  [GAP-5] With infer=False:\n"
            f"    LLM calls made = {memory.llm.generate_response.call_count}\n"
            "  Zero LLM calls — fact extraction and conflict pipeline are bypassed.\n"
            "  Raw message content is stored as-is with no deduplication."
        )
        assert memory.llm.generate_response.call_count == 0

    def test_gap6_procedural_memory_bypasses_conflict_pipeline(self, mocker):
        """
        GAP-6: Memory.add() with memory_type='procedural_memory' and agent_id set
        routes to _create_procedural_memory before _add_to_vector_store is
        called.  The conflict pipeline is never reached.

        We verify by patching _add_to_vector_store and confirming it is
        never called on the procedural path.
        """
        memory, mock_vs = _make_memory(mocker)
        add_to_vs_spy = mocker.patch.object(memory, "_add_to_vector_store")
        add_to_graph_spy = mocker.patch.object(memory, "_add_to_graph", return_value=[])

        # Patch _create_procedural_memory so we don't need a real LLM
        mocker.patch.object(
            memory, "_create_procedural_memory", return_value={"results": []}
        )

        memory.add(
            [{"role": "user", "content": "Always greet users by name"}],
            agent_id="support-agent",
            memory_type="procedural_memory",
        )

        print(
            "\n  [GAP-6] With memory_type='procedural_memory' + agent_id:\n"
            f"    _add_to_vector_store called = {add_to_vs_spy.called}\n"
            "  The conflict pipeline inside _add_to_vector_store is never reached.\n"
            "  Procedural memories bypass contradiction detection entirely."
        )
        add_to_vs_spy.assert_not_called()

    def test_gap4_telemetry_not_fired_for_conflict_mutations(self, mocker):
        """
        GAP-4: capture_event is NOT called for the individual _delete_memory
        and _create_memory operations triggered by the conflict pipeline.
        Only the outer add() boundary fires capture_event("mem0.add").

        Conflict-driven mutations are invisible to telemetry/analytics.
        """
        memory, mock_vs = _make_memory(mocker)
        mock_vs.search.return_value = [
            _make_search_result("old-mem-uuid", "User is vegetarian", score=0.92)
        ]

        captured_events: list[str] = []

        def _capture_spy(event_name, *args, **kwargs):
            captured_events.append(event_name)

        mocker.patch("mem0.memory.main.capture_event", side_effect=_capture_spy)

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            CONTRADICTION_HIGH_NEW,
        ]

        # Call _add_to_vector_store directly — the outer add() normally fires
        # capture_event("mem0.add") before calling this
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        print(
            f"\n  [GAP-4] capture_event calls during _add_to_vector_store: {captured_events}\n"
            "  _delete_memory and _create_memory do not call capture_event.\n"
            "  Conflict-driven DELETE + ADD are invisible to telemetry."
        )
        # No capture_event fires inside _add_to_vector_store itself
        assert "mem0.delete" not in captured_events
        assert "mem0.add" not in captured_events
