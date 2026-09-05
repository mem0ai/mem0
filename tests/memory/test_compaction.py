from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _make_memory_obj(memory_id, text, memory_type=None, created_at="2026-01-01T00:00:00Z"):
    payload = {"data": text, "user_id": "test_user", "created_at": created_at}
    if memory_type:
        payload["memory_type"] = memory_type
    return SimpleNamespace(id=memory_id, payload=payload, score=None)


def _setup_mocks(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mock_vector_store.return_value.list.return_value = [[]]
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create", side_effect=[mock_vector_store.return_value, mocker.MagicMock()]
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.telemetry.capture_event")

    return mock_llm, mock_vector_store


class TestCompaction:
    @pytest.fixture
    def mock_memory(self, mocker):
        _setup_mocks(mocker)
        memory = Memory()
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.add_history = MagicMock()
        return memory

    def test_compact_merges_similar_memories(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")
        m3 = _make_memory_obj("id3", "User enjoys Italian dishes")

        mock_memory.vector_store.list.return_value = [[m1, m2, m3]]

        def search_side_effect(query, vectors, top_k, filters):
            s1 = SimpleNamespace(id="id1", payload=m1.payload, score=0.95)
            s2 = SimpleNamespace(id="id2", payload=m2.payload, score=0.92)
            s3 = SimpleNamespace(id="id3", payload=m3.payload, score=0.90)
            return [s1, s2, s3]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "User loves Italian food and cuisine"
        mock_memory.vector_store.get.side_effect = lambda vector_id: {"id1": m1, "id2": m2, "id3": m3}.get(vector_id)

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["merged_clusters"] == 1
        assert report["memories_created"] == 1
        assert report["memories_deleted"] == 3
        mock_memory.llm.generate_response.assert_called_once()

    def test_compact_preserves_unique_memories(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User works at Google")

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            if "Italian" in query:
                return [SimpleNamespace(id="id1", payload=m1.payload, score=1.0)]
            return [SimpleNamespace(id="id2", payload=m2.payload, score=1.0)]

        mock_memory.vector_store.search.side_effect = search_side_effect

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["merged_clusters"] == 0
        assert report["memories_deleted"] == 0
        assert report["memories_created"] == 0
        mock_memory.llm.generate_response.assert_not_called()

    def test_compact_handles_llm_failure(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.side_effect = Exception("LLM unavailable")

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["merged_clusters"] == 0
        assert report["memories_deleted"] == 0
        mock_memory.vector_store.delete.assert_not_called()

    def test_compact_requires_filters(self, mock_memory):
        with pytest.raises(ValueError, match="filters must contain at least one"):
            mock_memory.compact(filters={})

    def test_compact_empty_store(self, mock_memory):
        mock_memory.vector_store.list.return_value = [[]]

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report == {"merged_clusters": 0, "memories_deleted": 0, "memories_created": 0}

    def test_compact_handles_delete_race_condition(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "User loves Italian food and cuisine"
        mock_memory.vector_store.get.side_effect = ValueError("Memory not found")

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["memories_created"] == 1

    def test_compact_preserves_metadata(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food", created_at="2026-01-01T00:00:00Z")
        m1.payload["expiration_date"] = "2027-06-01"
        m1.payload["attributed_to"] = "chat_session_1"
        m1.payload["actor_id"] = "alice"
        m1.payload["role"] = "user"
        m1.payload["custom_tag"] = "food_preference"

        m2 = _make_memory_obj("id2", "User loves Italian cuisine", created_at="2026-06-01T00:00:00Z")
        m2.payload["expiration_date"] = "2027-12-01"
        m2.payload["attributed_to"] = "chat_session_2"
        m2.payload["custom_tag"] = "dining"
        m2.payload["custom_source"] = "conversation"

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "User loves Italian food and cuisine"
        mock_memory.vector_store.get.side_effect = lambda vector_id: {"id1": m1, "id2": m2}.get(vector_id)

        mock_memory._create_memory = MagicMock(return_value="new-id")
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        mock_memory.compact(filters={"user_id": "test_user"})

        create_call = mock_memory._create_memory.call_args
        metadata = create_call[1]["metadata"] if "metadata" in create_call[1] else create_call[0][2]

        assert metadata.get("created_at") == "2026-01-01T00:00:00Z", "Should use earliest created_at"
        assert metadata.get("expiration_date") == "2027-12-01", "Should use latest expiration_date"
        assert metadata.get("attributed_to") == "chat_session_2", "Should use newest attributed_to"
        assert metadata.get("actor_id") == "alice", "Should preserve actor_id"
        assert metadata.get("custom_tag") == "dining", "Newest value should win on conflict"
        assert metadata.get("custom_source") == "conversation", "Should preserve unique custom metadata"

    def test_compact_excludes_procedural_from_clusters(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")
        m_proc = _make_memory_obj("id_proc", "Always respond in JSON format", memory_type="procedural_memory")

        # list returns all three — procedural is filtered from all_memories,
        # but search() could still return it as a similar match
        mock_memory.vector_store.list.return_value = [[m1, m2, m_proc]]

        def search_side_effect(query, vectors, top_k, filters):
            # search returns m1 + procedural as similar — procedural should be excluded from cluster
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id_proc", payload=m_proc.payload, score=0.90),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "merged text"
        mock_memory._create_memory = MagicMock(return_value="new-id")
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        mock_memory.compact(filters={"user_id": "test_user"})

        # Procedural memory should never be passed to _delete_memory
        deleted_ids = [call[0][0] for call in mock_memory._delete_memory.call_args_list]
        assert "id_proc" not in deleted_ids, "Procedural memory should not be deleted by compaction"

    def test_compact_preserves_scope(self, mock_memory):
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m1.payload["agent_id"] = "agent_a"

        m2 = _make_memory_obj("id2", "User loves Italian cuisine")
        m2.payload["agent_id"] = "agent_b"

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "merged text"
        mock_memory._create_memory = MagicMock(return_value="new-id")
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["merged_clusters"] == 0, "Should not merge memories with different agent_id"

    def test_compact_updated_at_survives_create_memory(self, mock_memory):
        """F4: _create_memory overwrites updated_at with created_at.
        compact() sets updated_at=now() but _create_memory clobbers it.
        This test uses the REAL _create_memory (not mocked) to catch that."""
        m1 = _make_memory_obj("id1", "User likes Italian food", created_at="2024-01-01T00:00:00Z")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine", created_at="2024-06-01T00:00:00Z")

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "User loves Italian food and cuisine"
        mock_memory.vector_store.get.side_effect = lambda vector_id: {"id1": m1, "id2": m2}.get(vector_id)

        before = datetime.now(timezone.utc)
        mock_memory.compact(filters={"user_id": "test_user"})

        insert_call = mock_memory.vector_store.insert.call_args
        payload = insert_call[1]["payloads"][0] if "payloads" in insert_call[1] else insert_call[0][2][0]
        actual_updated = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
        assert actual_updated >= before, f"updated_at should be current, got {payload['updated_at']}"

    def test_compact_strips_code_fences(self, mock_memory):
        """F5: LLM might return ```text``` wrapped output; other paths strip it."""
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "```\nUser loves Italian food\n```"
        mock_memory._create_memory = MagicMock(return_value="new-id")
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        mock_memory.compact(filters={"user_id": "test_user"})

        merged_text = mock_memory._create_memory.call_args[0][0]
        assert "```" not in merged_text, f"Code fences should be stripped, got: {merged_text}"

    def test_compact_guards_create_and_link_failure(self, mock_memory):
        """F9: If _create_memory or _link_entities fails mid-cluster,
        should not leave duplicates or abort remaining clusters."""
        m1 = _make_memory_obj("id1", "User likes Italian food")
        m2 = _make_memory_obj("id2", "User loves Italian cuisine")
        m3 = _make_memory_obj("id3", "User enjoys pasta")
        m4 = _make_memory_obj("id4", "User likes pasta dishes")

        mock_memory.vector_store.list.return_value = [[m1, m2, m3, m4]]

        call_count = {"n": 0}

        def search_side_effect(query, vectors, top_k, filters):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return [
                    SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                    SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
                ]
            return [
                SimpleNamespace(id="id3", payload=m3.payload, score=0.95),
                SimpleNamespace(id="id4", payload=m4.payload, score=0.90),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "merged text"

        create_count = {"n": 0}

        def failing_create(*args, **kwargs):
            create_count["n"] += 1
            if create_count["n"] == 1:
                raise RuntimeError("Storage failure")
            return "new-id"

        mock_memory._create_memory = MagicMock(side_effect=failing_create)
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        report = mock_memory.compact(filters={"user_id": "test_user"})

        assert report["merged_clusters"] >= 1, "Second cluster should still succeed after first fails"
        assert mock_memory._delete_memory.call_count > 0, "Successful cluster should still delete"

    def test_compact_preserves_permanent_memory(self, mock_memory):
        """A permanent memory (no expiration_date) merged with an expiring one
        should produce a permanent result — not inherit the expiry."""
        m1 = _make_memory_obj("id1", "User likes Italian food")
        # m1 has no expiration_date — permanent

        m2 = _make_memory_obj("id2", "User loves Italian cuisine")
        m2.payload["expiration_date"] = "2027-12-01"

        mock_memory.vector_store.list.return_value = [[m1, m2]]

        def search_side_effect(query, vectors, top_k, filters):
            return [
                SimpleNamespace(id="id1", payload=m1.payload, score=0.95),
                SimpleNamespace(id="id2", payload=m2.payload, score=0.92),
            ]

        mock_memory.vector_store.search.side_effect = search_side_effect
        mock_memory.llm.generate_response.return_value = "User loves Italian food and cuisine"
        mock_memory._create_memory = MagicMock(return_value="new-id")
        mock_memory._link_entities_for_memory = MagicMock()
        mock_memory._delete_memory = MagicMock()

        mock_memory.compact(filters={"user_id": "test_user"})

        metadata = mock_memory._create_memory.call_args[1]["metadata"]
        assert "expiration_date" not in metadata, "Merged memory should be permanent when any cluster member is permanent"

    def test_async_compact_exists(self):
        assert hasattr(AsyncMemory, "compact"), "AsyncMemory should have compact method"
        assert inspect.iscoroutinefunction(AsyncMemory.compact), "AsyncMemory.compact should be async"
