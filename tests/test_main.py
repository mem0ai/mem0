import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory


@pytest.fixture(autouse=True)
def mock_openai():
    os.environ["OPENAI_API_KEY"] = "123"
    with patch("openai.OpenAI") as mock:
        mock.return_value = Mock()
        yield mock


@pytest.fixture
def memory_instance():
    with (
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_vector_store.create.return_value.search.return_value = []
        mock_llm.create.return_value = Mock()

        config = MemoryConfig(version="v1.1")
        return Memory(config)


@pytest.fixture
def memory_custom_instance():
    with (
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_vector_store.create.return_value.search.return_value = []
        mock_llm.create.return_value = Mock()

        config = MemoryConfig(
            version="v1.1",
            custom_instructions="custom prompt extracting memory in json format",
        )
        return Memory(config)


def test_add(memory_instance):
    memory_instance._add_to_vector_store = Mock(return_value=[{"memory": "Test memory", "event": "ADD"}])

    result = memory_instance.add(messages=[{"role": "user", "content": "Test message"}], user_id="test_user")

    assert "results" in result
    assert result["results"] == [{"memory": "Test memory", "event": "ADD"}]

    memory_instance._add_to_vector_store.assert_called_once_with(
        [{"role": "user", "content": "Test message"}], {"user_id": "test_user"}, {"user_id": "test_user"}, True, prompt=None
    )


def test_get(memory_instance):
    mock_memory = Mock(
        id="test_id",
        payload={
            "data": "Test memory",
            "user_id": "test_user",
            "hash": "test_hash",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-02T00:00:00",
            "extra_field": "extra_value",
        },
    )
    memory_instance.vector_store.get = Mock(return_value=mock_memory)

    result = memory_instance.get("test_id")

    assert result["id"] == "test_id"
    assert result["memory"] == "Test memory"
    assert result["user_id"] == "test_user"
    assert result["hash"] == "test_hash"
    assert result["created_at"] == "2023-01-01T00:00:00"
    assert result["updated_at"] == "2023-01-02T00:00:00"
    assert result["metadata"] == {"extra_field": "extra_value"}


def test_search(memory_instance):
    mock_memories = [
        Mock(id="1", payload={"data": "Memory 1", "user_id": "test_user"}, score=0.9),
        Mock(id="2", payload={"data": "Memory 2", "user_id": "test_user"}, score=0.8),
    ]
    memory_instance.vector_store.search = Mock(return_value=mock_memories)
    memory_instance.vector_store.keyword_search = Mock(return_value=None)  # No BM25
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    with patch("mem0.memory.main.lemmatize_for_bm25", return_value="test query"), \
         patch("mem0.memory.main.extract_entities", return_value=[]):
        result = memory_instance.search("test query", filters={"user_id": "test_user"})

    assert "results" in result
    assert len(result["results"]) == 2
    assert result["results"][0]["id"] == "1"
    assert result["results"][0]["memory"] == "Memory 1"
    assert result["results"][0]["user_id"] == "test_user"
    # Score is now combined score (semantic only since no BM25/entity), still 0.9
    assert result["results"][0]["score"] == pytest.approx(0.9)

    # Hybrid pipeline over-fetches: max(20*4, 60) = 80 (top_k default is now 20)
    memory_instance.vector_store.search.assert_called_once_with(
        query="test query", vectors=[0.1, 0.2, 0.3], top_k=80, filters={"user_id": "test_user"}
    )


def test_update(memory_instance):
    memory_instance.embedding_model = Mock()
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    memory_instance._update_memory = Mock()

    result = memory_instance.update("test_id", "Updated memory")

    memory_instance._update_memory.assert_called_once_with(
        "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, None
    )

    assert result["message"] == "Memory updated successfully!"


def test_update_with_metadata(memory_instance):
    memory_instance.embedding_model = Mock()
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    memory_instance._update_memory = Mock()
    metadata = {"category": "sports", "priority": "high"}

    result = memory_instance.update("test_id", "Updated memory", metadata=metadata)

    memory_instance._update_memory.assert_called_once_with(
        "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, metadata
    )

    assert result["message"] == "Memory updated successfully!"


def test_update_with_empty_metadata(memory_instance):
    memory_instance.embedding_model = Mock()
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    memory_instance._update_memory = Mock()

    memory_instance.update("test_id", "Updated memory", metadata={})

    memory_instance._update_memory.assert_called_once_with(
        "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, {}
    )


def test_delete(memory_instance):
    memory_instance._delete_memory = Mock()

    result = memory_instance.delete("test_id")

    # delete() now fetches the memory first and passes it to _delete_memory
    existing_memory = memory_instance.vector_store.get.return_value
    memory_instance._delete_memory.assert_called_once_with("test_id", existing_memory)
    assert result["message"] == "Memory deleted successfully!"


def test_delete_all(memory_instance):
    mock_memories = [Mock(id="1"), Mock(id="2")]
    memory_instance.vector_store.list = Mock(return_value=(mock_memories, None))
    memory_instance.vector_store.reset = Mock()
    memory_instance._delete_memory = Mock()

    result = memory_instance.delete_all(user_id="test_user")

    assert memory_instance._delete_memory.call_count == 2
    # Ensure the collection is NOT dropped — only matched memories should be removed
    memory_instance.vector_store.reset.assert_not_called()

    assert result["message"] == "Memories deleted successfully!"


def test_get_all(memory_instance):
    mock_memories = [Mock(id="1", payload={"data": "Memory 1", "user_id": "test_user"})]
    memory_instance.vector_store.list = Mock(return_value=(mock_memories, None))

    result = memory_instance.get_all(filters={"user_id": "test_user"})

    assert isinstance(result, dict)
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "1"
    assert result["results"][0]["memory"] == "Memory 1"
    assert result["results"][0]["user_id"] == "test_user"

    memory_instance.vector_store.list.assert_called_once_with(filters={"user_id": "test_user"}, top_k=20)


def test_no_telemetry_vector_store_when_disabled():
    """VectorStoreFactory should only be called once (for user data) when telemetry is disabled."""
    with (
        patch("mem0.memory.main.MEM0_TELEMETRY", False),
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()

        config = MemoryConfig(version="v1.1")
        Memory(config)

        # VectorStoreFactory.create should be called exactly once — for user data only, not telemetry
        assert mock_vector_store.create.call_count == 1


def test_telemetry_vector_store_created_when_enabled():
    """VectorStoreFactory should be called twice (user data + telemetry) when telemetry is enabled."""
    with (
        patch("mem0.memory.main.MEM0_TELEMETRY", True),
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()

        config = MemoryConfig(version="v1.1")
        Memory(config)

        # VectorStoreFactory.create should be called twice — user data + telemetry
        assert mock_vector_store.create.call_count == 2


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestEntityIdValidation:
    """Tests for entity ID validation (whitespace rejection and trimming)."""

    def test_search_rejects_whitespace_only_user_id(self, memory_instance):
        """Search should reject whitespace-only user_id in filters."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot be empty"):
            memory_instance.search("test query", filters={"user_id": "   "})

    def test_search_rejects_internal_whitespace_user_id(self, memory_instance):
        """Search should reject user_id with internal whitespace."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot contain whitespace"):
            memory_instance.search("test query", filters={"user_id": "user 123"})

    def test_search_rejects_tab_in_user_id(self, memory_instance):
        """Search should reject user_id with tab character."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot contain whitespace"):
            memory_instance.search("test query", filters={"user_id": "user\t123"})

    def test_get_all_rejects_whitespace_only_user_id(self, memory_instance):
        """get_all should reject whitespace-only user_id in filters."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot be empty"):
            memory_instance.get_all(filters={"user_id": "   "})

    def test_get_all_rejects_internal_whitespace_user_id(self, memory_instance):
        """get_all should reject user_id with internal whitespace."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot contain whitespace"):
            memory_instance.get_all(filters={"user_id": "user 123"})

    def test_add_rejects_whitespace_only_user_id(self, memory_instance):
        """add should reject whitespace-only user_id."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot be empty"):
            memory_instance.add("test message", user_id="   ")

    def test_add_rejects_internal_whitespace_user_id(self, memory_instance):
        """add should reject user_id with internal whitespace."""
        with pytest.raises(ValueError, match="Invalid user_id.*cannot contain whitespace"):
            memory_instance.add("test message", user_id="user 123")


class TestSearchParamValidation:
    """Tests for search parameter validation (threshold and top_k)."""

    def test_search_rejects_threshold_above_1(self, memory_instance):
        """Search should reject threshold > 1."""
        with pytest.raises(ValueError, match="Invalid threshold.*Must be between 0 and 1"):
            memory_instance.search("test query", filters={"user_id": "test"}, threshold=1.5)

    def test_search_rejects_negative_threshold(self, memory_instance):
        """Search should reject negative threshold."""
        with pytest.raises(ValueError, match="Invalid threshold.*Must be between 0 and 1"):
            memory_instance.search("test query", filters={"user_id": "test"}, threshold=-0.5)

    def test_search_rejects_negative_top_k(self, memory_instance):
        """Search should reject negative top_k."""
        with pytest.raises(ValueError, match="Invalid top_k.*Must be a non-negative"):
            memory_instance.search("test query", filters={"user_id": "test"}, top_k=-5)

    def test_get_all_rejects_negative_top_k(self, memory_instance):
        """get_all should reject negative top_k."""
        with pytest.raises(ValueError, match="Invalid top_k.*Must be a non-negative"):
            memory_instance.get_all(filters={"user_id": "test"}, top_k=-1)

    def test_search_accepts_threshold_zero(self, memory_instance):
        """Search should accept threshold=0 (edge case)."""
        mock_memories = []
        memory_instance.vector_store.search = Mock(return_value=mock_memories)
        memory_instance.vector_store.keyword_search = Mock(return_value=None)
        memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

        with patch("mem0.memory.main.lemmatize_for_bm25", return_value="test"), \
             patch("mem0.memory.main.extract_entities", return_value=[]):
            result = memory_instance.search("test", filters={"user_id": "test"}, threshold=0)

        assert "results" in result

    def test_search_accepts_threshold_one(self, memory_instance):
        """Search should accept threshold=1.0 (edge case)."""
        mock_memories = []
        memory_instance.vector_store.search = Mock(return_value=mock_memories)
        memory_instance.vector_store.keyword_search = Mock(return_value=None)
        memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

        with patch("mem0.memory.main.lemmatize_for_bm25", return_value="test"), \
             patch("mem0.memory.main.extract_entities", return_value=[]):
            result = memory_instance.search("test", filters={"user_id": "test"}, threshold=1.0)

        assert "results" in result

    def test_search_accepts_top_k_zero(self, memory_instance):
        """Search should accept top_k=0."""
        mock_memories = []
        memory_instance.vector_store.search = Mock(return_value=mock_memories)
        memory_instance.vector_store.keyword_search = Mock(return_value=None)
        memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

        with patch("mem0.memory.main.lemmatize_for_bm25", return_value="test"), \
             patch("mem0.memory.main.extract_entities", return_value=[]):
            result = memory_instance.search("test", filters={"user_id": "test"}, top_k=0)

        assert "results" in result
