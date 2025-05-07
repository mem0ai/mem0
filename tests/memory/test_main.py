import hashlib
import json
import logging
from unittest.mock import MagicMock

import pytest
from qdrant_client.http.models.models import Record, ScoredPoint

from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Helper to setup common mocks for both sync and async fixtures"""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create", side_effect=[mock_vector_store.return_value, mocker.MagicMock()]
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm, mock_vector_store


def get_vector_payload(memory_payload, vector_id):
    """Helper to get payload from memory_payload dict"""
    return memory_payload.get(vector_id)


def update_mock_record(memory_payload, vector_id, vector, payload):
    """Update a mock Record object for vector_store.update"""
    old_payload = get_vector_payload(memory_payload, vector_id)
    if old_payload:
        old_payload.update(payload)
        return Record(id=vector_id, payload=old_payload, vector=vector, shard_key=None, order_value=None)
    return None


def insert_mock_record(memory_payload, vectors, ids, payloads):
    """Insert a mock Record object for vector_store.insert
    Args:
        memory_payload: The memory payload to insert.
        vectors: The vectors to insert.
        ids: The IDs to insert.
        payloads: The payloads to insert.
    """
    if vectors and ids and payloads:
        return Record(id=ids[0], payload=payloads[0], vector=vectors[0], shard_key=None, order_value=None)
    return None


def create_mock_record(memory_payload, vector_id):
    """Create a mock Record object for vector_store.get"""
    payload = get_vector_payload(memory_payload, vector_id)
    if payload:
        return Record(id=vector_id, payload=payload, vector=None, shard_key=None, order_value=None)
    return None


def create_mock_scored_point(memory_payload, vector_id):
    """Create a mock ScoredPoint object for vector_store.search"""
    payload = get_vector_payload(memory_payload, vector_id)
    if payload:
        return ScoredPoint(
            id=vector_id, version=57, score=0.9, payload=payload, vector=None, shard_key=None, order_value=None
        )
    return None


@pytest.fixture
def base_memory_scenario():
    """Returns (memory_payload, llm_responses, id_mapping)"""
    memory_payload = {
        "5e6c2501-095c-49b4-8e59-348cf6745f1d": {
            "user_id": "default_user",
            "data": "I like rice and beans",
            "hash": hashlib.md5("I like rice and beans".encode()).hexdigest(),
            "created_at": "2025-05-07T00:21:28.118301-07:00",
        },
        "f179d243-6875-4a91-a278-5d153e2ca193": {
            "user_id": "default_user",
            "data": "Likes rice",
            "hash": hashlib.md5("Likes rice".encode()).hexdigest(),
            "created_at": "2025-05-07T00:21:28.118301-07:00",
        },
        "27b6bd28-2e23-4c2e-9715-1a46b00362cd": {
            "user_id": "default_user",
            "data": "I like basmati rice",
            "hash": hashlib.md5("I like basmati rice".encode()).hexdigest(),
            "created_at": "2025-05-07T00:21:28.118301-07:00",
        },
        "43d356c7-6833-4c27-abff-2876cc37b144": {
            "user_id": "default_user",
            "data": "I like acro yoga, surfing, swimming, and paddle boarding.",
            "hash": hashlib.md5("I like acro yoga, surfing, swimming, and paddle boarding.".encode()).hexdigest(),
            "created_at": "2025-05-07T00:21:28.118301-07:00",
        },
        "be6c8333-2e75-4177-a9b6-6a2a5d75dd32": {
            "user_id": "default_user",
            "data": "Likes pizza",
            "hash": hashlib.md5("Likes pizza".encode()).hexdigest(),
            "created_at": "2025-05-07T00:21:28.118301-07:00",
        },
    }

    llm_responses = [
        '{"facts": ["I like rice and beans and cheese", "I like tacos"]}',
        json.dumps(
            {
                "memory": [
                    {
                        "id": "0",
                        "text": "I like rice and beans and cheese",
                        "event": "UPDATE",
                        "old_memory": "I like rice and beans",
                    },
                    {"id": "1", "text": "Likes rice", "event": "NONE"},
                    {"id": "2", "text": "I like basmati rice", "event": "NONE"},
                    {
                        "id": "3",
                        "text": "I like acro yoga, surfing, swimming, and paddle boarding.",
                        "event": "NONE",
                    },
                    {"id": "4", "text": "Likes pizza", "event": "NONE"},
                    {"id": "5", "text": "Likes tacos", "event": "ADD"},
                ]
            }
        ),
    ]

    id_mapping = {
        "0": "5e6c2501-095c-49b4-8e59-348cf6745f1d",
        "1": "f179d243-6875-4a91-a278-5d153e2ca193",
        "2": "27b6bd28-2e23-4c2e-9715-1a46b00362cd",
        "3": "43d356c7-6833-4c27-abff-2876cc37b144",
        "4": "be6c8333-2e75-4177-a9b6-6a2a5d75dd32",
    }

    return memory_payload, llm_responses, id_mapping


class TestAddToVectorStoreErrors:
    @pytest.fixture
    def mock_memory(self, mocker):
        """Fixture that returns a Memory instance with mocker-based mocks"""
        mock_llm, _ = _setup_mocks(mocker)

        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_fact_extraction_prompt = None
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    def test_valid_llm_response_fact_extraction(self, mock_memory, caplog, base_memory_scenario):
        """Test valid response from LLM during fact extraction"""
        memory_payload, llm_responses, id_mapping = base_memory_scenario

        from functools import partial

        mock_get = partial(create_mock_record, memory_payload)
        mock_search = partial(create_mock_scored_point, memory_payload)
        mock_update = partial(update_mock_record, memory_payload)
        mock_insert = partial(insert_mock_record, memory_payload)
        mock_memory.vector_store.insert.side_effect = mock_insert

        mock_memory.vector_store.get.side_effect = mock_get
        mock_memory.vector_store.search.return_value = [mock_search(key) for key in memory_payload.keys()]
        mock_memory.vector_store.update.side_effect = mock_update

        mock_memory.llm.generate_response.side_effect = llm_responses

        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        assert mock_memory.llm.generate_response.call_count == 2
        assert len(result) == 2
        assert result[0]["memory"] == "I like rice and beans and cheese"
        assert result[0]["event"] == "UPDATE"
        assert result[1]["memory"] == "Likes tacos"
        assert result[1]["event"] == "ADD"
        assert mock_memory.vector_store.update.call_count == 1
        assert mock_memory.vector_store.update.call_args[1]["payload"]["data"] == "I like rice and beans and cheese"
        assert (
            mock_memory.vector_store.update.call_args[1]["payload"]["hash"]
            == hashlib.md5("I like rice and beans and cheese".encode()).hexdigest()
        )
        assert mock_memory.vector_store.insert.call_args[1]["payloads"][0]["data"] == "Likes tacos"
        assert (
            mock_memory.vector_store.insert.call_args[1]["payloads"][0]["hash"]
            == hashlib.md5("Likes tacos".encode()).hexdigest()
        )

    def test_empty_llm_response_memory_actions(self, mock_memory, caplog, base_memory_scenario):
        """Test empty response from LLM during memory actions"""
        memory_payload, _, id_mapping = base_memory_scenario

        from functools import partial

        mock_get = partial(create_mock_record, memory_payload)
        mock_search = partial(create_mock_scored_point, memory_payload)
        mock_memory.vector_store.get.side_effect = mock_get
        mock_memory.vector_store.search.return_value = [mock_search(key) for key in memory_payload.keys()]

        mock_memory.llm.generate_response.side_effect = ["", ""]

        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        assert result == []
        assert "Invalid JSON response" in caplog.text
        assert "Error in new_retrieved_facts:" in caplog.text
        assert mock_memory.vector_store.update.call_count == 0
        assert mock_memory.vector_store.insert.call_count == 0


@pytest.mark.asyncio
class TestAsyncAddToVectorStoreErrors:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        """Fixture for AsyncMemory with mocker-based mocks"""
        mock_llm, _ = _setup_mocks(mocker)

        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_fact_extraction_prompt = None
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    @pytest.mark.asyncio
    async def test_async_valid_llm_response_fact_extraction(
        self, mock_async_memory, caplog, mocker, base_memory_scenario
    ):
        """Test valid response in AsyncMemory._add_to_vector_store"""
        memory_payload, llm_responses, id_mapping = base_memory_scenario

        from functools import partial

        mock_get = partial(create_mock_record, memory_payload)
        mock_search = partial(create_mock_scored_point, memory_payload)
        mock_update = partial(update_mock_record, memory_payload)
        mock_insert = partial(insert_mock_record, memory_payload)
        mock_async_memory.vector_store.insert.side_effect = mock_insert

        mock_async_memory.vector_store.get.side_effect = mock_get
        mock_async_memory.vector_store.search.return_value = [mock_search(key) for key in memory_payload.keys()]
        mock_async_memory.vector_store.update.side_effect = mock_update

        mock_async_memory.llm.generate_response.side_effect = llm_responses

        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        assert mock_async_memory.llm.generate_response.call_count == 2
        assert len(result) == 2
        assert result[0]["memory"] == "I like rice and beans and cheese"
        assert result[0]["event"] == "UPDATE"
        assert result[1]["memory"] == "Likes tacos"
        assert result[1]["event"] == "ADD"
        assert mock_async_memory.vector_store.update.call_count == 1
        assert (
            mock_async_memory.vector_store.update.call_args[1]["payload"]["data"] == "I like rice and beans and cheese"
        )
        assert (
            mock_async_memory.vector_store.update.call_args[1]["payload"]["hash"]
            == hashlib.md5("I like rice and beans and cheese".encode()).hexdigest()
        )
        assert mock_async_memory.vector_store.insert.call_args[1]["payloads"][0]['data'] == "Likes tacos"
        assert (
            mock_async_memory.vector_store.insert.call_args[1]["payloads"][0]["hash"]
            == hashlib.md5("Likes tacos".encode()).hexdigest()
        )
        assert mock_async_memory.vector_store.insert.call_count == 1
        assert mock_async_memory.vector_store.insert.call_args[1]["vectors"] == [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]]

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_memory_actions(
        self, mock_async_memory, caplog, mocker, base_memory_scenario
    ):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        memory_payload, _, id_mapping = base_memory_scenario

        from functools import partial

        mock_get = partial(create_mock_record, memory_payload)
        mock_search = partial(create_mock_scored_point, memory_payload)
        mock_async_memory.vector_store.get.side_effect = mock_get
        mock_async_memory.vector_store.search.return_value = [mock_search(key) for key in memory_payload.keys()]

        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.side_effect = ["", ""]

        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        assert result == []
        assert "Invalid JSON response" in caplog.text
        assert "Error in new_retrieved_facts:" in caplog.text
        assert mock_async_memory.vector_store.update.call_count == 0
        assert mock_async_memory.vector_store.insert.call_count == 0
