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

    def test_valid_llm_response_fact_extraction(self, mock_memory, caplog, mocker):
        """Test valid response from LLM during fact extraction"""

        # Setup
        memory_payload_lookup = {
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
                "hash": hashlib.md5(
                    "I like acro yoga, surfing, swimming, and paddle boarding.".encode()
                ).hexdigest(),
                "created_at": "2025-05-07T00:21:28.118301-07:00",
            },
            "be6c8333-2e75-4177-a9b6-6a2a5d75dd32": {
                "user_id": "default_user",
                "data": "Likes pizza",
                "hash": hashlib.md5("Likes pizza".encode()).hexdigest(),
                "created_at": "2025-05-07T00:21:28.118301-07:00",
            },
        }

        def get_vector_payload(vector_id):
            return memory_payload_lookup.get(vector_id)

        def get_vector_store(vector_id):
            payload = get_vector_payload(vector_id)
            if payload:
                return Record(id=vector_id, payload=payload, vector=None, shard_key=None, order_value=None)
            return None
        
        def get_vector_payload_record(vector_id):
            payload = get_vector_payload(vector_id)
            if payload:
                return ScoredPoint(id=vector_id, version=57, score=0.9, payload=payload, vector=None, shard_key=None, order_value=None)
            return None

        mock_memory.vector_store.get.side_effect = get_vector_store
        mock_memory.vector_store.search.return_value = [
            get_vector_payload_record(key) for key in memory_payload_lookup.keys()
        ]
        # Mock the LLM response
        mock_memory.llm.generate_response.side_effect = [
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
        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify
        assert mock_memory.llm.generate_response.call_count == 2
        assert len(result) == 2

        assert result[0]["memory"] == "I like rice and beans and cheese"
        assert result[0]["event"] == "UPDATE"
        assert result[1]["memory"] == "Likes tacos"
        assert result[1]["event"] == "ADD"

    def test_empty_llm_response_memory_actions(self, mock_memory, caplog):
        """Test empty response from LLM during memory actions"""
        # Setup
        # First call returns valid JSON, second call returns empty string
        mock_memory.llm.generate_response.side_effect = [
            '',
            '',
        ]

        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify
        assert result == []
        assert "Invalid JSON response" in caplog.text


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
    async def test_async_valid_llm_response_fact_extraction(self, mock_async_memory, caplog, mocker):
        """Test valid response in AsyncMemory._add_to_vector_store"""
        memory_payload_lookup = {
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
                "hash": hashlib.md5(
                    "I like acro yoga, surfing, swimming, and paddle boarding.".encode()
                ).hexdigest(),
                "created_at": "2025-05-07T00:21:28.118301-07:00",
            },
            "be6c8333-2e75-4177-a9b6-6a2a5d75dd32": {
                "user_id": "default_user",
                "data": "Likes pizza",
                "hash": hashlib.md5("Likes pizza".encode()).hexdigest(),
                "created_at": "2025-05-07T00:21:28.118301-07:00",
            },
        }

        def get_vector_payload(vector_id):
            return memory_payload_lookup.get(vector_id)

        def get_vector_store(vector_id):
            payload = get_vector_payload(vector_id)
            if payload:
                return Record(id=vector_id, payload=payload, vector=None, shard_key=None, order_value=None)
            return None
        
        def get_vector_payload_record(vector_id):
            payload = get_vector_payload(vector_id)
            if payload:
                return ScoredPoint(id=vector_id, version=57, score=0.9, payload=payload, vector=None, shard_key=None, order_value=None)
            return None

        mock_async_memory.vector_store.get.side_effect = get_vector_store
        mock_async_memory.vector_store.search.return_value = [
            get_vector_payload_record(key) for key in memory_payload_lookup.keys()
        ]
        mock_async_memory.llm.generate_response.side_effect = [
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

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_memory_actions(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.side_effect = [
            '',
            '',
        ]

        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        assert result == []
        assert "Invalid JSON response" in caplog.text
