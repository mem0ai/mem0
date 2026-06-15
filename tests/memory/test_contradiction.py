import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.return_value.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mock_vector_store.return_value.keyword_search.return_value = None
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm, mock_vector_store


def _make_existing_result(mem_id, data, mem_hash="abc123"):
    return SimpleNamespace(
        id=mem_id,
        score=0.9,
        payload={"data": data, "hash": mem_hash, "created_at": "2025-01-01T00:00:00+00:00"},
    )


class TestContradictionResolution:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, mock_vs = _setup_mocks(mocker)
        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.add_history = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    def test_contradiction_supersedes_old_memory(self, mock_memory, mocker):
        """When LLM returns contradicts_memory_ids, the old memory gets is_superseded=True."""
        mocker.patch("mem0.memory.main.capture_event")

        old_id = "old-uuid-1234"
        old_result = _make_existing_result(old_id, "User is a vegetarian")
        mock_memory.vector_store.search.return_value = [old_result]

        mock_memory.vector_store.get.return_value = SimpleNamespace(
            id=old_id,
            payload={"data": "User is a vegetarian", "hash": "oldhash"},
        )

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User had a steak dinner and enjoyed it",
                    "attributed_to": "user",
                    "contradicts_memory_ids": ["0"],
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I had a great steak dinner last night"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        mock_memory.vector_store.update.assert_called_once()
        update_call = mock_memory.vector_store.update.call_args
        assert update_call.kwargs["vector_id"] == old_id
        updated_payload = update_call.kwargs["payload"]
        assert updated_payload["is_superseded"] is True
        assert "superseded_at" in updated_payload

        mock_memory.db.add_history.assert_called_once()
        history_call = mock_memory.db.add_history.call_args
        assert history_call[0][0] == old_id
        assert history_call[0][1] == "User is a vegetarian"
        assert history_call[0][2] is None
        assert history_call[0][3] == "DELETE"

        add_events = [r for r in result if r["event"] == "ADD"]
        contradiction_events = [r for r in result if r["event"] == "CONTRADICTION_RESOLVED"]
        assert len(add_events) == 1
        assert len(contradiction_events) == 1
        assert contradiction_events[0]["id"] == old_id
        assert contradiction_events[0]["memory"] == "User is a vegetarian"
        assert "steak" in contradiction_events[0]["superseded_by"]

    def test_no_contradiction_no_side_effects(self, mock_memory, mocker):
        """When no contradicts_memory_ids, no vector_store.update or DELETE history."""
        mocker.patch("mem0.memory.main.capture_event")

        mock_memory.vector_store.search.return_value = []

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User likes hiking",
                    "attributed_to": "user",
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love hiking"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        mock_memory.vector_store.update.assert_not_called()
        mock_memory.db.add_history.assert_not_called()
        assert all(r["event"] == "ADD" for r in result)

    def test_contradiction_invalid_id_ignored(self, mock_memory, mocker):
        """contradicts_memory_ids with IDs not in uuid_mapping are gracefully skipped."""
        mocker.patch("mem0.memory.main.capture_event")

        mock_memory.vector_store.search.return_value = []

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User now works at Meta",
                    "attributed_to": "user",
                    "contradicts_memory_ids": ["99"],
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I just started at Meta"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        mock_memory.vector_store.update.assert_not_called()
        mock_memory.vector_store.get.assert_not_called()
        assert len(result) == 1
        assert result[0]["event"] == "ADD"

    def test_multiple_contradictions(self, mock_memory, mocker):
        """One new memory contradicts two existing ones -- both get superseded."""
        mocker.patch("mem0.memory.main.capture_event")

        old1 = _make_existing_result("uuid-veg", "User is a vegetarian", "hash1")
        old2 = _make_existing_result("uuid-no-meat", "User avoids all meat products", "hash2")
        mock_memory.vector_store.search.return_value = [old1, old2]

        mock_memory.vector_store.get.side_effect = [
            SimpleNamespace(id="uuid-veg", payload={"data": "User is a vegetarian", "hash": "hash1"}),
            SimpleNamespace(id="uuid-no-meat", payload={"data": "User avoids all meat products", "hash": "hash2"}),
        ]

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User had steak dinner and enjoyed it",
                    "attributed_to": "user",
                    "contradicts_memory_ids": ["0", "1"],
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Had a great steak dinner"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        assert mock_memory.vector_store.update.call_count == 2
        assert mock_memory.db.add_history.call_count == 2
        contradiction_events = [r for r in result if r["event"] == "CONTRADICTION_RESOLVED"]
        assert len(contradiction_events) == 2
        superseded_ids = {e["id"] for e in contradiction_events}
        assert superseded_ids == {"uuid-veg", "uuid-no-meat"}

    def test_contradiction_vector_store_get_fails_gracefully(self, mock_memory, mocker):
        """If vector_store.get raises, the contradiction is skipped and ADD still works."""
        mocker.patch("mem0.memory.main.capture_event")

        old = _make_existing_result("uuid-old", "User works at Google")
        mock_memory.vector_store.search.return_value = [old]
        mock_memory.vector_store.get.side_effect = Exception("connection error")

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User now works at Meta",
                    "attributed_to": "user",
                    "contradicts_memory_ids": ["0"],
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Started at Meta"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        mock_memory.vector_store.update.assert_not_called()
        add_events = [r for r in result if r["event"] == "ADD"]
        assert len(add_events) == 1

    def test_contradiction_with_linked_memory_ids(self, mock_memory, mocker):
        """A memory can have both linked_memory_ids and contradicts_memory_ids."""
        mocker.patch("mem0.memory.main.capture_event")

        old1 = _make_existing_result("uuid-google", "User works at Google", "hash1")
        old2 = _make_existing_result("uuid-engineer", "User is a software engineer", "hash2")
        mock_memory.vector_store.search.return_value = [old1, old2]

        mock_memory.vector_store.get.return_value = SimpleNamespace(
            id="uuid-google",
            payload={"data": "User works at Google", "hash": "hash1"},
        )

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User started working at Meta as a software engineer",
                    "attributed_to": "user",
                    "linked_memory_ids": ["1"],
                    "contradicts_memory_ids": ["0"],
                }
            ]
        })
        mock_memory.llm.generate_response.return_value = llm_response

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I started at Meta as an engineer"}],
            metadata={},
            filters={"user_id": "test"},
            infer=True,
        )

        mock_memory.vector_store.update.assert_called_once()
        update_payload = mock_memory.vector_store.update.call_args.kwargs["payload"]
        assert update_payload["is_superseded"] is True

        add_events = [r for r in result if r["event"] == "ADD"]
        contradiction_events = [r for r in result if r["event"] == "CONTRADICTION_RESOLVED"]
        assert len(add_events) == 1
        assert len(contradiction_events) == 1


class TestSupersededFilteredFromSearch:
    def test_superseded_excluded_from_search_candidates(self):
        """Memories with is_superseded=True should be excluded from search results."""
        candidates_input = [
            {"id": "1", "score": 0.9, "payload": {"data": "Active memory"}},
            {"id": "2", "score": 0.85, "payload": {"data": "Superseded memory", "is_superseded": True}},
            {"id": "3", "score": 0.8, "payload": {"data": "Another active memory"}},
        ]

        filtered = [c for c in candidates_input if not c["payload"].get("is_superseded")]
        assert len(filtered) == 2
        assert all(c["id"] != "2" for c in filtered)

    def test_superseded_excluded_from_get_all(self):
        """_get_all_from_vector_store skips memories with is_superseded=True."""
        active_mem = SimpleNamespace(
            id="active-1",
            payload={"data": "Active memory", "hash": "h1", "created_at": "2025-01-01", "updated_at": "2025-01-01"},
        )
        superseded_mem = SimpleNamespace(
            id="super-1",
            payload={
                "data": "Old memory",
                "hash": "h2",
                "created_at": "2025-01-01",
                "updated_at": "2025-01-01",
                "is_superseded": True,
            },
        )

        memories = [active_mem, superseded_mem]
        filtered = [m for m in memories if not (hasattr(m, "payload") and m.payload and m.payload.get("is_superseded"))]
        assert len(filtered) == 1
        assert filtered[0].id == "active-1"


@pytest.mark.asyncio
class TestAsyncContradictionResolution:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        _setup_mocks(mocker)
        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.add_history = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    @pytest.mark.asyncio
    async def test_async_contradiction_supersedes_old_memory(self, mock_async_memory, mocker):
        """Async pipeline handles contradicts_memory_ids the same as sync."""
        mocker.patch("mem0.memory.main.capture_event")

        old_id = "old-uuid-async"
        old_result = _make_existing_result(old_id, "User is a vegetarian")
        mock_async_memory.vector_store.search.return_value = [old_result]

        mock_async_memory.vector_store.get.return_value = SimpleNamespace(
            id=old_id,
            payload={"data": "User is a vegetarian", "hash": "oldhash"},
        )

        llm_response = json.dumps({
            "memory": [
                {
                    "id": "0",
                    "text": "User had a steak dinner and enjoyed it",
                    "attributed_to": "user",
                    "contradicts_memory_ids": ["0"],
                }
            ]
        })
        mock_async_memory.llm.generate_response.return_value = llm_response

        result = await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I had a great steak dinner"}],
            metadata={},
            effective_filters={"user_id": "test"},
            infer=True,
        )

        mock_async_memory.vector_store.update.assert_called_once()
        update_call = mock_async_memory.vector_store.update.call_args
        assert update_call.kwargs["vector_id"] == old_id
        updated_payload = update_call.kwargs["payload"]
        assert updated_payload["is_superseded"] is True

        add_events = [r for r in result if r["event"] == "ADD"]
        contradiction_events = [r for r in result if r["event"] == "CONTRADICTION_RESOLVED"]
        assert len(add_events) == 1
        assert len(contradiction_events) == 1
        assert contradiction_events[0]["id"] == old_id
