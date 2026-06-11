"""Tests for ``scoping_metadata_keys`` on Memory.add / AsyncMemory.add (#5121).

Covers the helper, validation, the two-app repro from the issue, the
default-unchanged baseline, and the async mirror.
"""

from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory, _build_session_scope


def _setup_mocks(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.return_value.embed_batch.return_value = [[0.1, 0.2, 0.3]]
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
    mocker.patch("mem0.memory.main.capture_event")
    return mock_llm, mock_vector_store


def _make_sync_memory(mocker):
    mock_llm, _ = _setup_mocks(mocker)
    mock_llm.return_value.generate_response.return_value = '{"memory": []}'
    memory = Memory()
    memory.config = mocker.MagicMock()
    memory.custom_instructions = None
    memory.api_version = "v1.1"
    memory.db.get_last_messages = MagicMock(return_value=[])
    memory.db.save_messages = MagicMock()
    return memory


def _make_async_memory(mocker):
    mock_llm, _ = _setup_mocks(mocker)
    mock_llm.return_value.generate_response.return_value = '{"memory": []}'
    memory = AsyncMemory()
    memory.config = mocker.MagicMock()
    memory.custom_instructions = None
    memory.api_version = "v1.1"
    memory.db.get_last_messages = MagicMock(return_value=[])
    memory.db.save_messages = MagicMock()
    return memory


class TestBuildSessionScope:
    """Pure unit tests for the scope-string helper."""

    def test_default_three_key_scope_unchanged(self):
        # Backward-compat baseline: no extra keys -> legacy 3-key format.
        scope = _build_session_scope({"user_id": "u1", "agent_id": "a1", "run_id": "r1"})
        assert scope == "agent_id=a1&run_id=r1&user_id=u1"

    def test_empty_scoping_filters_unchanged(self):
        scope = _build_session_scope({"user_id": "u1"}, scoping_filters={})
        assert scope == "user_id=u1"

    def test_none_scoping_filters_unchanged(self):
        scope = _build_session_scope({"user_id": "u1"}, scoping_filters=None)
        assert scope == "user_id=u1"

    def test_scope_includes_extra_keys_sorted(self):
        scope = _build_session_scope(
            {"user_id": "u1"},
            scoping_filters={"app_id": "app-a"},
        )
        assert scope == "app_id=app-a&user_id=u1"

    def test_two_apps_produce_disjoint_scopes(self):
        a = _build_session_scope({"user_id": "u1"}, scoping_filters={"app_id": "app-a"})
        b = _build_session_scope({"user_id": "u1"}, scoping_filters={"app_id": "app-b"})
        assert a != b


class TestScopingMetadataKeysValidation:
    """Surface misuse of ``scoping_metadata_keys`` loudly instead of silently no-op'ing."""

    def test_bare_string_raises_type_error(self, mocker):
        memory = _make_sync_memory(mocker)
        with pytest.raises(TypeError, match="bare string"):
            memory.add(
                messages=[{"role": "user", "content": "x"}],
                user_id="user-1",
                metadata={"app_id": "app-a"},
                scoping_metadata_keys="app_id",
            )

    @pytest.mark.parametrize("reserved", ["user_id", "agent_id", "run_id"])
    def test_session_id_key_raises_value_error(self, mocker, reserved):
        memory = _make_sync_memory(mocker)
        with pytest.raises(ValueError, match="session-id keys"):
            memory.add(
                messages=[{"role": "user", "content": "x"}],
                user_id="user-1",
                metadata={"app_id": "app-a", reserved: "spoofed"},
                scoping_metadata_keys=[reserved, "app_id"],
            )

    def test_tuple_and_set_are_accepted(self, mocker):
        # Type signature says List[str] but any iterable-of-strings should work.
        memory = _make_sync_memory(mocker)
        memory.add(
            messages=[{"role": "user", "content": "x"}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=("app_id",),
        )
        assert memory.vector_store.search.call_args.kwargs["filters"] == {
            "user_id": "user-1",
            "app_id": "app-a",
        }


class TestSyncAddDefaultBehaviorUnchanged:
    """Without ``scoping_metadata_keys``, behavior must match current main."""

    def test_phase1_search_filters_only_session_ids(self, mocker):
        memory = _make_sync_memory(mocker)

        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
        )

        search_kwargs = memory.vector_store.search.call_args.kwargs
        assert search_kwargs["filters"] == {"user_id": "user-1"}, (
            "Default-behavior baseline: app_id must NOT leak into Phase 1 filters "
            "when scoping_metadata_keys is not supplied."
        )

    def test_session_scope_only_session_ids(self, mocker):
        memory = _make_sync_memory(mocker)

        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
        )

        save_messages_args = memory.db.save_messages.call_args[0]
        session_scope = save_messages_args[1]
        assert session_scope == "user_id=user-1"


class TestSyncAddWithScopingMetadataKeys:
    """Opt-in path: scoping_metadata_keys must thread into Phase 1 + SQLite."""

    @pytest.fixture
    def memory(self, mocker):
        return _make_sync_memory(mocker)

    def test_phase1_search_filter_includes_app_id(self, memory):
        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=["app_id"],
        )

        search_kwargs = memory.vector_store.search.call_args.kwargs
        assert search_kwargs["filters"] == {"user_id": "user-1", "app_id": "app-a"}

    def test_session_scope_includes_app_id(self, memory):
        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=["app_id"],
        )

        session_scope = memory.db.save_messages.call_args[0][1]
        assert session_scope == "app_id=app-a&user_id=user-1"

    def test_two_apps_produce_isolated_scopes_and_filters(self, memory):
        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=["app_id"],
        )
        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-b"},
            scoping_metadata_keys=["app_id"],
        )

        first_search, second_search = memory.vector_store.search.call_args_list
        assert first_search.kwargs["filters"]["app_id"] == "app-a"
        assert second_search.kwargs["filters"]["app_id"] == "app-b"

        first_save, second_save = memory.db.save_messages.call_args_list
        assert first_save[0][1] != second_save[0][1]
        assert "app_id=app-a" in first_save[0][1]
        assert "app_id=app-b" in second_save[0][1]

    def test_missing_metadata_value_is_skipped(self, memory):
        # If a key is named but not present in metadata (or set to None / ""),
        # skip it rather than raising. Matches how empty session ids are handled.
        memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": None, "tenant_id": "t1"},
            scoping_metadata_keys=["app_id", "tenant_id"],
        )

        search_kwargs = memory.vector_store.search.call_args.kwargs
        assert search_kwargs["filters"] == {"user_id": "user-1", "tenant_id": "t1"}


@pytest.mark.asyncio
class TestAsyncAddWithScopingMetadataKeys:
    """Mirror of the sync opt-in path on AsyncMemory.add."""

    async def test_async_default_phase1_filters_unchanged(self, mocker):
        memory = _make_async_memory(mocker)
        await memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
        )
        search_kwargs = memory.vector_store.search.call_args.kwargs
        assert search_kwargs["filters"] == {"user_id": "user-1"}

    async def test_async_phase1_includes_app_id_when_opted_in(self, mocker):
        memory = _make_async_memory(mocker)
        await memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=["app_id"],
        )
        search_kwargs = memory.vector_store.search.call_args.kwargs
        assert search_kwargs["filters"] == {"user_id": "user-1", "app_id": "app-a"}

    async def test_async_session_scope_includes_app_id_when_opted_in(self, mocker):
        memory = _make_async_memory(mocker)
        await memory.add(
            messages=[{"role": "user", "content": "prefers dark mode."}],
            user_id="user-1",
            metadata={"app_id": "app-a"},
            scoping_metadata_keys=["app_id"],
        )
        session_scope = memory.db.save_messages.call_args[0][1]
        assert session_scope == "app_id=app-a&user_id=user-1"
