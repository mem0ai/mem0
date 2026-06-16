"""Tests for the `project` scope field in the mem0 core (add/search/get_all).

Covers, for both `Memory` (sync) and `AsyncMemory` (async):
- write persists `project` into the payload metadata sent to the vector store;
- `search()` adds a `project` filter to the query;
- `get_all()` applies a `project` filter;
- omitting `project` keeps the previous behavior (no `project` filter, no crash);
- `project` coexists with `user_id` without conflict.

Also unit-tests the `_build_filters_and_metadata` helper directly.
"""

from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory, _build_filters_and_metadata


def _setup_mocks(mocker):
    """Mock embedder, vector store and LLM, mirroring tests/memory/test_main.py."""
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
    mocker.patch("mem0.memory.main.capture_event")

    return mock_llm, mock_vector_store


@pytest.fixture
def memory(mocker):
    _setup_mocks(mocker)
    mem = Memory()
    mem.db.get_last_messages = MagicMock(return_value=[])
    mem.db.save_messages = MagicMock()
    return mem


@pytest.fixture
def async_memory(mocker):
    _setup_mocks(mocker)
    mem = AsyncMemory()
    mem.db.get_last_messages = MagicMock(return_value=[])
    mem.db.save_messages = MagicMock()
    return mem


def _inserted_payloads(vector_store):
    """Collect all payloads passed to vector_store.insert across calls."""
    payloads = []
    for call in vector_store.insert.call_args_list:
        payloads.extend(call.kwargs.get("payloads", []))
    return payloads


# --------------------------------------------------------------------------- #
# _build_filters_and_metadata helper
# --------------------------------------------------------------------------- #
class TestBuildFiltersAndMetadataProject:
    def test_project_added_to_metadata_and_filters(self):
        metadata, filters = _build_filters_and_metadata(user_id="alice", project="proj_a")
        assert metadata["project"] == "proj_a"
        assert filters["project"] == "proj_a"
        # session id preserved alongside project
        assert metadata["user_id"] == "alice"
        assert filters["user_id"] == "alice"

    def test_project_omitted_keeps_behavior(self):
        metadata, filters = _build_filters_and_metadata(user_id="alice")
        assert "project" not in metadata
        assert "project" not in filters

    def test_project_alone_does_not_satisfy_session_requirement(self):
        # project must not count as a session identifier (backward compatible validation)
        with pytest.raises(Exception):
            _build_filters_and_metadata(project="proj_a")

    def test_project_is_keyword_only(self):
        with pytest.raises(TypeError):
            # positional args are not allowed (keyword-only signature)
            _build_filters_and_metadata("alice", "agent", "run", "proj")


# --------------------------------------------------------------------------- #
# Memory.add (sync) — write path
# --------------------------------------------------------------------------- #
class TestSyncAddPersistsProject:
    def test_add_includes_project_in_payload(self, memory):
        memory.add("I like coffee", user_id="alice", project="proj_a", infer=False)

        payloads = _inserted_payloads(memory.vector_store)
        assert payloads, "expected at least one payload inserted"
        assert all(p.get("project") == "proj_a" for p in payloads)
        # coexists with user_id
        assert all(p.get("user_id") == "alice" for p in payloads)

    def test_add_without_project_has_no_project_key(self, memory):
        memory.add("I like tea", user_id="alice", infer=False)

        payloads = _inserted_payloads(memory.vector_store)
        assert payloads
        assert all("project" not in p for p in payloads)


# --------------------------------------------------------------------------- #
# Memory.search / get_all (sync) — read path
# --------------------------------------------------------------------------- #
class TestSyncSearchAndGetAllFilterProject:
    def test_search_adds_project_filter(self, memory):
        memory.search("coffee", filters={"user_id": "alice"}, project="proj_a")
        # search delegates to vector_store.search(filters=...)
        filters = memory.vector_store.search.call_args.kwargs["filters"]
        assert filters["project"] == "proj_a"
        assert filters["user_id"] == "alice"

    def test_search_without_project_has_no_filter(self, memory):
        memory.search("coffee", filters={"user_id": "alice"})
        filters = memory.vector_store.search.call_args.kwargs["filters"]
        assert "project" not in filters

    def test_get_all_applies_project_filter(self, memory):
        memory.vector_store.list.return_value = []
        memory.get_all(filters={"user_id": "alice"}, project="proj_a")
        filters = memory.vector_store.list.call_args.kwargs["filters"]
        assert filters["project"] == "proj_a"
        assert filters["user_id"] == "alice"

    def test_get_all_without_project_has_no_filter(self, memory):
        memory.vector_store.list.return_value = []
        memory.get_all(filters={"user_id": "alice"})
        filters = memory.vector_store.list.call_args.kwargs["filters"]
        assert "project" not in filters


# --------------------------------------------------------------------------- #
# AsyncMemory equivalents
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestAsyncProject:
    async def test_async_add_includes_project_in_payload(self, async_memory):
        await async_memory.add("I like coffee", user_id="alice", project="proj_a", infer=False)
        payloads = _inserted_payloads(async_memory.vector_store)
        assert payloads
        assert all(p.get("project") == "proj_a" for p in payloads)
        assert all(p.get("user_id") == "alice" for p in payloads)

    async def test_async_add_without_project(self, async_memory):
        await async_memory.add("I like tea", user_id="alice", infer=False)
        payloads = _inserted_payloads(async_memory.vector_store)
        assert payloads
        assert all("project" not in p for p in payloads)

    async def test_async_search_adds_project_filter(self, async_memory):
        await async_memory.search("coffee", filters={"user_id": "alice"}, project="proj_a")
        filters = async_memory.vector_store.search.call_args.kwargs["filters"]
        assert filters["project"] == "proj_a"
        assert filters["user_id"] == "alice"

    async def test_async_search_without_project(self, async_memory):
        await async_memory.search("coffee", filters={"user_id": "alice"})
        filters = async_memory.vector_store.search.call_args.kwargs["filters"]
        assert "project" not in filters

    async def test_async_get_all_applies_project_filter(self, async_memory):
        async_memory.vector_store.list.return_value = []
        await async_memory.get_all(filters={"user_id": "alice"}, project="proj_a")
        filters = async_memory.vector_store.list.call_args.kwargs["filters"]
        assert filters["project"] == "proj_a"
        assert filters["user_id"] == "alice"

    async def test_async_get_all_without_project(self, async_memory):
        async_memory.vector_store.list.return_value = []
        await async_memory.get_all(filters={"user_id": "alice"})
        filters = async_memory.vector_store.list.call_args.kwargs["filters"]
        assert "project" not in filters
