import logging
from unittest.mock import MagicMock, patch

import pytest

from mem0.memory.main import AsyncMemory, Memory


class TestAddToVectorStoreErrors:
    @pytest.fixture
    def mock_memory(self):
        """Fixture that returns a Memory instance with properly mocked dependencies"""
        # Mock telemetry first
        with patch('mem0.memory.telemetry.capture_event') as mock_capture:
            mock_capture.return_value = None
            # Mock all factories before instantiation
            mock_embedder = MagicMock()
            mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
            with patch('mem0.utils.factory.EmbedderFactory.create', mock_embedder):
                mock_vector_store = MagicMock()
                mock_vector_store.return_value.search.return_value = []
                with patch('mem0.utils.factory.VectorStoreFactory.create', mock_vector_store):
                    mock_llm = MagicMock()
                    with patch('mem0.utils.factory.LlmFactory.create', mock_llm):
                        mock_db = MagicMock()
                        with patch('mem0.memory.storage.SQLiteManager', mock_db):
                            # Mock telemetry vector store separately
                            with patch('mem0.utils.factory.VectorStoreFactory.create', 
                                    return_value=MagicMock(), 
                                    side_effect=[mock_vector_store.return_value, MagicMock()]):
                                # Now instantiate Memory
                                memory = Memory()
                                
                                # Configure mocks
                                memory.config = MagicMock()
                                memory.config.custom_fact_extraction_prompt = None
                                memory.config.custom_update_memory_prompt = None
                                memory.api_version = "v1.1"
                                
                                return memory

    def test_empty_llm_response_fact_extraction(self, mock_memory, caplog):
        """Test empty response from LLM during fact extraction"""
        # Setup
        mock_memory.llm.generate_response.return_value = ""
        
        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
                filters={},
                infer=True
            )
        
        # Verify
        assert mock_memory.llm.generate_response.call_count == 2
        assert result == []  # Should return empty list when no memories processed
        assert "Error in new_retrieved_facts" in caplog.text

    def test_empty_llm_response_memory_actions(self, mock_memory, caplog):
        """Test empty response from LLM during memory actions"""
        # Setup
        # First call returns valid JSON, second call returns empty string
        mock_memory.llm.generate_response.side_effect = [
            '{"facts": ["test fact"]}',
            ""
        ]
        
        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
                filters={},
                infer=True
            )
        
        # Verify
        assert mock_memory.llm.generate_response.call_count == 2
        assert result == []  # Should return empty list when no memories processed
        assert "Invalid JSON response" in caplog.text


@pytest.mark.asyncio
class TestAsyncAddToVectorStoreErrors:
    @pytest.fixture
    def mock_async_memory(self):
        """Fixture for AsyncMemory with properly mocked dependencies"""
        # Mock telemetry first
        with patch('mem0.memory.telemetry.capture_event') as mock_capture:
            mock_capture.return_value = None
            # Mock all factories before instantiation
            mock_embedder = MagicMock()
            mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
            with patch('mem0.utils.factory.EmbedderFactory.create', mock_embedder):
                mock_vector_store = MagicMock()
                mock_vector_store.return_value.search.return_value = []
                with patch('mem0.utils.factory.VectorStoreFactory.create', mock_vector_store):
                    mock_llm = MagicMock()
                    with patch('mem0.utils.factory.LlmFactory.create', mock_llm):
                        mock_db = MagicMock()
                        with patch('mem0.memory.storage.SQLiteManager', mock_db):
                            # Mock telemetry vector store separately
                            with patch('mem0.utils.factory.VectorStoreFactory.create', 
                                    return_value=MagicMock(), 
                                    side_effect=[mock_vector_store.return_value, MagicMock()]):
                                # Now instantiate AsyncMemory
                                memory = AsyncMemory()
                                
                                # Configure mocks
                                memory.config = MagicMock()
                                memory.config.custom_fact_extraction_prompt = None
                                memory.config.custom_update_memory_prompt = None
                                memory.api_version = "v1.1"
                                
                                return memory

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_fact_extraction(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        mocker.patch('mem0.utils.factory.EmbedderFactory.create', return_value=MagicMock())
        mock_async_memory.llm.generate_response.return_value = ""
        
        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
                filters={},
                infer=True
            )
        
        assert result == []
        assert "Error in new_retrieved_facts" in caplog.text

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_memory_actions(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        mocker.patch('mem0.utils.factory.EmbedderFactory.create', return_value=MagicMock())
        mock_async_memory.llm.generate_response.side_effect = [
            '{"facts": ["test fact"]}',
            ""
        ]
        
        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}],
                metadata={},
                filters={},
                infer=True
            )
        
        assert result == []
        assert "Invalid JSON response" in caplog.text
