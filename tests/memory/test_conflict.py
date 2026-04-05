"""
Tests for conflict detection and resolution pipeline in mem0.
Follows the _setup_mocks pattern from tests/memory/test_main.py.
"""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

import mem0.memory.conflict as conflict_module
from mem0.memory.conflict import (
    ConflictResolution,
    _execute_merge_llm_call,
    apply_auto_resolution,
)
from mem0.memory.main import AsyncMemory, Memory


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _setup_mocks(mocker):
    """Setup factory-level mocks so Memory/AsyncMemory instantiation is clean."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm, mock_vector_store


def _make_mem_result(mem_id: str, text: str, score: float):
    """Create a mock vector search result with .id, .payload, .score."""
    mem = MagicMock()
    mem.id = mem_id
    mem.payload = {"data": text}
    mem.score = score
    return mem


def _make_memory(mocker, *, hitl_enabled=False, strategy="keep-higher-confidence"):
    """Create a Memory instance with mocked factories and conflict config set."""
    _, mock_vector_store = _setup_mocks(mocker)
    memory = Memory()
    memory.config.conflict_detection.hitl_enabled = hitl_enabled
    memory.config.conflict_detection.auto_resolve_strategy = strategy
    memory.config.conflict_detection.similarity_threshold = 0.85
    memory.config.conflict_detection.top_k = 20
    memory.config.session_id = "test-session-id"
    # Mock _delete_memory and _create_memory so tests don't hit the real vector store
    memory._delete_memory = mocker.MagicMock(return_value="old-mem-uuid")
    memory._create_memory = mocker.MagicMock(return_value="new-mem-uuid")
    return memory, mock_vector_store


@pytest.fixture(autouse=True)
def clear_session_overrides():
    """Clear module-level session overrides before and after each test."""
    conflict_module._session_overrides.clear()
    yield
    conflict_module._session_overrides.clear()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestConflictAutoResolution:
    def test_true_contradiction_auto_resolve_keep_higher_confidence(self, mocker):
        """confidence_new=0.7 > confidence_old=0.3 → KEEP_NEW"""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Cannot be vegetarian and eat chicken",
            "proposed_action": "Replace old memory with new fact",
            "confidence_new": 0.7,
            "confidence_old": 0.3,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',  # extraction
            contradiction_response,                         # classification
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_called_once()
        args, kwargs = memory._create_memory.call_args
        assert kwargs.get("data", args[0] if args else None) == "User eats chicken regularly"

    def test_true_contradiction_auto_resolve_keep_old_wins(self, mocker):
        """confidence_new=0.3 < confidence_old=0.8 → KEEP_OLD, no delete/create"""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Conflicting dietary preferences",
            "proposed_action": "Keep existing memory",
            "confidence_new": 0.3,
            "confidence_old": 0.8,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            contradiction_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken"}],
            metadata={},
            filters={},
            infer=True,
        )

        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()

    def test_nuance_skips_single_pass_update_llm(self, mocker):
        """NUANCE classification does not invoke update-memory LLM path."""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User prefers vegetarian meals", score=0.90)
        mock_vector_store.return_value.search.return_value = [old_mem]

        nuance_response = json.dumps({
            "conflict_class": "NUANCE",
            "explanation": "New fact adds detail without contradiction",
            "proposed_action": "Keep both in view",
            "confidence_new": 0.6,
            "confidence_old": 0.6,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User sometimes avoids meat"]}',  # extraction
            nuance_response,                               # classification
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I sometimes avoid meat"}],
            metadata={},
            filters={},
            infer=True,
        )

        # Two LLM calls: extraction + classification (single-pass update LLM removed)
        assert memory.llm.generate_response.call_count == 2
        # No delete path for NUANCE
        memory._delete_memory.assert_not_called()
        # Unhandled facts are now directly inserted
        memory._create_memory.assert_called_once()

    def test_none_classification_skips_single_pass_update_llm(self, mocker):
        """NONE classification does not invoke update-memory LLM path."""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User likes jazz music", score=0.87)
        mock_vector_store.return_value.search.return_value = [old_mem]

        none_response = json.dumps({
            "conflict_class": "NONE",
            "explanation": "No meaningful relationship",
            "proposed_action": "No action needed",
            "confidence_new": 0.4,
            "confidence_old": 0.4,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User prefers Italian food"]}',
            none_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love Italian food"}],
            metadata={},
            filters={},
            infer=True,
        )

        assert memory.llm.generate_response.call_count == 2
        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_called_once()

    def test_below_threshold_still_runs_classification(self, mocker):
        """Similarity threshold is ignored; classification still runs."""
        memory, mock_vector_store = _make_memory(mocker)

        low_score_mem = _make_mem_result("old-mem-uuid", "User likes jazz", score=0.60)
        mock_vector_store.return_value.search.return_value = [low_score_mem]

        none_response = json.dumps({
            "conflict_class": "NONE",
            "explanation": "No conflict",
            "proposed_action": "No action",
            "confidence_new": 0.5,
            "confidence_old": 0.5,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User likes coffee"]}',  # extraction
            none_response,                       # classification (even below former threshold)
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I like coffee"}],
            metadata={},
            filters={},
            infer=True,
        )

        # 2 calls: extraction + classification (single-pass update LLM removed)
        assert memory.llm.generate_response.call_count == 2
        memory._create_memory.assert_called_once()


class TestHITL:
    def test_hitl_always_replace_persists_within_session(self, mocker):
        """First contradiction: user picks always-replace. Second: prompt NOT shown."""
        memory, mock_vector_store = _make_memory(mocker, hitl_enabled=True)

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Conflicting dietary info",
            "proposed_action": "Replace with new fact",
            "confidence_new": 0.7,
            "confidence_old": 0.4,
        })

        # Patch builtins.input so the real hitl_prompt_sync runs and stores the override
        memory.config.session_id = "hitl-test-session"
        input_mock = mocker.patch("builtins.input", return_value="always-replace")
        mocker.patch("mem0.memory.conflict._print_hitl_block")  # suppress stdout

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )
        assert input_mock.call_count == 1

        # Second contradiction in same session — override stored, prompt must NOT fire
        memory._delete_memory.reset_mock()
        memory._create_memory.reset_mock()
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User loves BBQ"]}',
            contradiction_response,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love BBQ"}],
            metadata={},
            filters={},
            infer=True,
        )

        # input still called only once — session override bypassed prompt
        assert input_mock.call_count == 1
        # But KEEP_NEW resolution executed automatically
        memory._delete_memory.assert_called_once()


class TestAsyncConflict:
    @pytest.mark.asyncio
    async def test_async_contradiction_resolution(self, mocker):
        """AsyncMemory: CONTRADICTION with confidence_new>confidence_old → KEEP_NEW"""
        mock_embedder = mocker.MagicMock()
        mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

        mock_vector_store = mocker.MagicMock()
        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]
        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
        )

        mock_llm = mocker.MagicMock()
        mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

        memory = AsyncMemory()
        memory.config.conflict_detection.hitl_enabled = False
        memory.config.conflict_detection.auto_resolve_strategy = "keep-higher-confidence"
        memory.config.conflict_detection.similarity_threshold = 0.85
        memory.config.conflict_detection.top_k = 20
        memory.config.session_id = "async-test-session"
        memory._delete_memory = mocker.AsyncMock(return_value="old-mem-uuid")
        memory._create_memory = mocker.AsyncMock(return_value="new-mem-uuid")

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Cannot be vegetarian and eat chicken",
            "proposed_action": "Replace old memory",
            "confidence_new": 0.7,
            "confidence_old": 0.3,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            contradiction_response,
        ]

        await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            effective_filters={},
            infer=True,
        )

        memory._delete_memory.assert_awaited_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_awaited_once()


class TestMergeStrategy:
    def test_merge_strategy_calls_merge_llm(self, mocker):
        """strategy=merge → third LLM call made, merged_text from LLM used"""
        memory, mock_vector_store = _make_memory(mocker, strategy="merge")

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "Conflicting dietary info",
            "proposed_action": "Merge both facts",
            "confidence_new": 0.6,
            "confidence_old": 0.6,
        })
        merge_response = json.dumps({"merged": "User follows a mostly plant-based diet but occasionally eats chicken"})

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

        # All three LLM calls fired
        assert memory.llm.generate_response.call_count == 3
        # Old memory deleted, merged text created
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        args, kwargs = memory._create_memory.call_args
        created_data = kwargs.get("data", args[0] if args else None)
        assert created_data == "User follows a mostly plant-based diet but occasionally eats chicken"

    def test_merge_strategy_fallback_on_llm_failure(self, mocker):
        """Merge LLM fails → merged_text is [MERGE PENDING] placeholder, no exception raised"""
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


class TestAuditHistory:
    def test_audit_history_written_on_keep_new(self, mocker):
        """KEEP_NEW: _delete_memory and _create_memory called (they write db.add_history internally)"""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "replace",
            "confidence_new": 0.8,
            "confidence_old": 0.2,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )

        # _delete_memory and _create_memory are the audit-writing actions
        memory._delete_memory.assert_called_once_with(memory_id="old-mem-uuid")
        memory._create_memory.assert_called_once()

    def test_audit_history_not_written_on_keep_old(self, mocker):
        """KEEP_OLD: no _delete_memory or _create_memory called"""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-mem-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "keep old",
            "confidence_new": 0.2,
            "confidence_old": 0.9,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )

        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()


class TestMultiMatch:
    def test_multi_match_pairs_resolved_independently(self, mocker):
        """One new_fact matches two old memories above threshold; resolved independently."""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem_1 = _make_mem_result("old-uuid-1", "User is vegetarian", score=0.93)
        old_mem_2 = _make_mem_result("old-uuid-2", "User avoids all animal products", score=0.89)
        mock_vector_store.return_value.search.return_value = [old_mem_1, old_mem_2]

        # First pair → KEEP_NEW (confidence_new wins)
        contradiction_keep_new = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict A",
            "proposed_action": "replace",
            "confidence_new": 0.8,
            "confidence_old": 0.3,
        })
        # Second pair → KEEP_OLD (confidence_old wins)
        contradiction_keep_old = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict B",
            "proposed_action": "keep old",
            "confidence_new": 0.3,
            "confidence_old": 0.9,
        })

        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats chicken regularly"]}',
            contradiction_keep_new,
            contradiction_keep_old,
            # no single-pass call — fact was handled (KEEP_NEW fired)
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat chicken regularly"}],
            metadata={},
            filters={},
            infer=True,
        )

        # Both classification calls made
        assert memory.llm.generate_response.call_count == 3

        # Delete called once (KEEP_NEW for old-uuid-1), not for old-uuid-2
        assert memory._delete_memory.call_count == 1
        memory._delete_memory.assert_called_with(memory_id="old-uuid-1")

        # New fact created once (from KEEP_NEW)
        assert memory._create_memory.call_count == 1


# ---------------------------------------------------------------------------
# S2 — Resolution strategy edge cases
# ---------------------------------------------------------------------------

class TestResolutionStrategies:
    def test_keep_newer_strategy(self, mocker):
        """keep-newer always resolves KEEP_NEW even when confidence_old is higher."""
        memory, mock_vector_store = _make_memory(mocker, strategy="keep-newer")

        old_mem = _make_mem_result("old-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "replace",
            "confidence_new": 0.2,
            "confidence_old": 0.9,  # old wins on confidence, but keep-newer ignores it
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction_response,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={},
            filters={},
            infer=True,
        )

        memory._delete_memory.assert_called_once_with(memory_id="old-uuid")
        memory._create_memory.assert_called_once()

    def test_keep_higher_confidence_tie_favors_new(self):
        """Equal confidence scores → KEEP_NEW (ties favour new information)."""
        cr = ConflictResolution(
            new_fact="User eats chicken",
            old_memory_id="old-id",
            old_memory_text="User is vegetarian",
            conflict_class="CONTRADICTION",
            explanation="conflict",
            proposed_action="keep newer",
            confidence_new=0.5,
            confidence_old=0.5,
            auto_resolved=False,
            resolution="",
            merged_text=None,
        )
        result = apply_auto_resolution(cr, "keep-higher-confidence")
        assert result.resolution == "KEEP_NEW"
        assert result.auto_resolved is True


# ---------------------------------------------------------------------------
# S1 — HITL scenarios (y, n, always-keep, invalid input)
# ---------------------------------------------------------------------------

class TestHITLScenarios:
    def _setup(self, mocker):
        memory, mock_vector_store = _make_memory(mocker, hitl_enabled=True)
        memory.config.session_id = "hitl-scenarios-session"
        mocker.patch("mem0.memory.conflict._print_hitl_block")
        old_mem = _make_mem_result("old-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]
        contradiction = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "Replace with new fact",
            "confidence_new": 0.7,
            "confidence_old": 0.4,
        })
        return memory, contradiction

    def test_hitl_y_resolves_keep_new(self, mocker):
        """User enters 'y' → old deleted, new fact created."""
        memory, contradiction = self._setup(mocker)
        mocker.patch("builtins.input", return_value="y")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )

        memory._delete_memory.assert_called_once_with(memory_id="old-uuid")
        memory._create_memory.assert_called_once()

    def test_hitl_n_resolves_keep_old(self, mocker):
        """User enters 'n' → no delete, no create."""
        memory, contradiction = self._setup(mocker)
        mocker.patch("builtins.input", return_value="n")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )

        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()

    def test_hitl_always_keep_persists_within_session(self, mocker):
        """'always-keep' on first contradiction → prompt not shown on second, resolves KEEP_OLD."""
        memory, contradiction = self._setup(mocker)
        input_mock = mocker.patch("builtins.input", return_value="always-keep")
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )
        assert input_mock.call_count == 1
        memory._delete_memory.assert_not_called()  # KEEP_OLD

        # Second contradiction — prompt must NOT fire
        memory._delete_memory.reset_mock()
        memory._create_memory.reset_mock()
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User loves BBQ"]}',
            contradiction,
        ]
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love BBQ"}],
            metadata={}, filters={}, infer=True,
        )

        assert input_mock.call_count == 1  # not called again
        memory._delete_memory.assert_not_called()  # still KEEP_OLD

    def test_hitl_invalid_input_defaults_to_n(self, mocker):
        """Two invalid inputs → defaults to 'n' → KEEP_OLD, no exception raised."""
        memory, contradiction = self._setup(mocker)
        mocker.patch("builtins.input", side_effect=["garbage", "also-garbage"])
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',
            contradiction,
        ]

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )

        memory._delete_memory.assert_not_called()
        memory._create_memory.assert_not_called()


# ---------------------------------------------------------------------------
# S3 — add() return shape unchanged after contradiction resolution
# ---------------------------------------------------------------------------

class TestAddReturnShape:
    def test_add_return_shape_unchanged_after_keep_new(self, mocker):
        """Memory.add() returns {"results": list} with no conflict-specific keys."""
        memory, mock_vector_store = _make_memory(mocker)

        old_mem = _make_mem_result("old-uuid", "User is vegetarian", score=0.92)
        mock_vector_store.return_value.search.return_value = [old_mem]

        contradiction_response = json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflict",
            "proposed_action": "replace",
            "confidence_new": 0.8,
            "confidence_old": 0.2,
        })
        memory.llm.generate_response.side_effect = [
            '{"facts": ["User eats steak"]}',  # extraction
            contradiction_response,             # classification → KEEP_NEW
        ]

        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I eat steak"}],
            metadata={}, filters={}, infer=True,
        )

        # _add_to_vector_store returns a list; Memory.add() wraps it in {"results": ...}
        # Verify no conflict keys leak into what would be returned
        if isinstance(result, dict):
            assert "results" in result
            for key in result:
                assert key not in ("conflicts", "resolutions", "conflict_resolutions")
        else:
            # Returns a list — no conflict objects present
            assert isinstance(result, list)
            for item in result:
                assert "conflict_class" not in item
                assert "resolution" not in item


# ---------------------------------------------------------------------------
# S4 — Env var overrides
# ---------------------------------------------------------------------------

class TestEnvVarOverrides:
    def test_env_var_overrides_defaults(self, monkeypatch):
        """Environment variables override ConflictDetectionConfig defaults."""
        monkeypatch.setenv("MEM0_CONFLICT_SIMILARITY_THRESHOLD", "0.70")
        monkeypatch.setenv("MEM0_CONFLICT_TOP_K", "10")
        monkeypatch.setenv("MEM0_CONFLICT_AUTO_RESOLVE_STRATEGY", "keep-newer")
        monkeypatch.setenv("MEM0_CONFLICT_HITL_ENABLED", "true")

        # Re-import to pick up new env vars (default_factory reads at instantiation)
        from mem0.configs.base import ConflictDetectionConfig
        config = ConflictDetectionConfig()

        assert config.similarity_threshold == 0.70
        assert config.top_k == 10
        assert config.auto_resolve_strategy == "keep-newer"
        assert config.hitl_enabled is True
