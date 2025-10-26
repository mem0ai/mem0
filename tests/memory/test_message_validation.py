"""Essential message validation tests for Memory and AsyncMemory classes."""

import pytest
from unittest.mock import Mock, patch
from mem0.exceptions import ValidationError as Mem0ValidationError
from mem0.memory.main import Memory, AsyncMemory
from mem0.configs.base import MemoryConfig


class TestMessageValidation:
    """Test message validation for Memory and AsyncMemory classes."""

    @pytest.fixture
    def memory_instance(self):
        """Create Memory instance with mocked dependencies."""
        config = MemoryConfig()
        with patch('mem0.memory.main.EmbedderFactory') as mock_embedder, \
             patch('mem0.memory.main.VectorStoreFactory') as mock_vector, \
             patch('mem0.memory.main.LlmFactory') as mock_llm, \
             patch('mem0.memory.main.SQLiteManager') as mock_db, \
             patch('mem0.memory.main.GraphStoreFactory') as mock_graph, \
             patch('mem0.memory.main.VectorStoreFactory') as mock_telemetry:
            
            mock_embedder.create.return_value = Mock()
            mock_vector.create.return_value = Mock()
            mock_llm.create.return_value = Mock()
            mock_db.return_value = Mock()
            mock_graph.create.return_value = None
            mock_telemetry.create.return_value = Mock()
            
            yield Memory(config)

    @pytest.fixture
    def async_memory_instance(self):
        """Create AsyncMemory instance with mocked dependencies."""
        config = MemoryConfig()
        with patch('mem0.memory.main.EmbedderFactory') as mock_embedder, \
             patch('mem0.memory.main.VectorStoreFactory') as mock_vector, \
             patch('mem0.memory.main.LlmFactory') as mock_llm, \
             patch('mem0.memory.main.SQLiteManager') as mock_db, \
             patch('mem0.memory.main.GraphStoreFactory') as mock_graph, \
             patch('mem0.memory.main.VectorStoreFactory') as mock_telemetry:
            
            mock_embedder.create.return_value = Mock()
            mock_vector.create.return_value = Mock()
            mock_llm.create.return_value = Mock()
            mock_db.return_value = Mock()
            mock_graph.create.return_value = None
            mock_telemetry.create.return_value = Mock()
            
            yield AsyncMemory(config)

    # Message Type Validation
    def test_valid_message_types(self, memory_instance):
        """Test valid message types."""
        # String message
        result = memory_instance.add("Hello", user_id="test")
        assert result is not None
        
        # Dict message
        result = memory_instance.add({"role": "user", "content": "Hello"}, user_id="test")
        assert result is not None
        
        # List message
        result = memory_instance.add([{"role": "user", "content": "Hello"}], user_id="test")
        assert result is not None

    def test_invalid_message_types(self, memory_instance):
        """Test invalid message types raise ValidationError."""
        # None message
        with pytest.raises(Mem0ValidationError) as exc_info:
            memory_instance.add(None, user_id="test")
        assert exc_info.value.error_code == "VALIDATION_003"
        
        # Integer message
        with pytest.raises(Mem0ValidationError) as exc_info:
            memory_instance.add(123, user_id="test")
        assert exc_info.value.error_code == "VALIDATION_003"
        
        # List of strings - this will fail in parse_vision_messages, not validation
        with pytest.raises(TypeError):
            memory_instance.add(["hello", "world"], user_id="test")

    # Session ID Validation
    def test_no_session_ids(self, memory_instance):
        """Test missing session IDs raises ValidationError."""
        with pytest.raises(Mem0ValidationError) as exc_info:
            memory_instance.add("Hello")
        assert exc_info.value.error_code == "VALIDATION_001"

    def test_valid_session_ids(self, memory_instance):
        """Test valid session IDs."""
        # user_id
        result = memory_instance.add("Hello", user_id="test")
        assert result is not None
        
        # agent_id
        result = memory_instance.add("Hello", agent_id="test")
        assert result is not None
        
        # run_id
        result = memory_instance.add("Hello", run_id="test")
        assert result is not None

    # Memory Type Validation
    def test_invalid_memory_type(self, memory_instance):
        """Test invalid memory_type raises ValidationError."""
        with pytest.raises(Mem0ValidationError) as exc_info:
            memory_instance.add("Hello", user_id="test", memory_type="invalid")
        assert exc_info.value.error_code == "VALIDATION_002"

    # AsyncMemory Tests
    @pytest.mark.asyncio
    async def test_async_invalid_message_type(self, async_memory_instance):
        """Test AsyncMemory with invalid message type."""
        with pytest.raises(Mem0ValidationError) as exc_info:
            await async_memory_instance.add(123, user_id="test")
        assert exc_info.value.error_code == "VALIDATION_003"

    @pytest.mark.asyncio
    async def test_async_no_session_ids(self, async_memory_instance):
        """Test AsyncMemory with no session IDs."""
        with pytest.raises(Mem0ValidationError) as exc_info:
            await async_memory_instance.add("Hello")
        assert exc_info.value.error_code == "VALIDATION_001"
