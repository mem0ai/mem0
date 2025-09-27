from unittest.mock import MagicMock, patch

import pytest

from mem0 import AsyncMemory, Memory
from mem0.memory.utils import remove_thinking_tags


def test_remove_thinking_tags():
    # with thinking tag
    assert remove_thinking_tags('<think>abc</think>{"facts":["test fact"]}') == '{"facts":["test fact"]}'
    
    # thinking content with multiple lines
    assert remove_thinking_tags('<think>\nabc\n</think>\n{"facts":["test fact"]}') == '{"facts":["test fact"]}'
    
    # more than one thinking tag(rare in practice)
    assert remove_thinking_tags('<think>A</think><think>B</think>{"facts":["test fact"]}') == '{"facts":["test fact"]}'
    
    # no tag
    assert remove_thinking_tags('{"facts":["test fact"]}') == '{"facts":["test fact"]}'




def create_mocked_memory():
    """Create a fully mocked Memory instance for testing."""
    with patch('mem0.utils.factory.LlmFactory.create') as mock_llm_factory, \
         patch('mem0.utils.factory.EmbedderFactory.create') as mock_embedder_factory, \
         patch('mem0.utils.factory.VectorStoreFactory.create') as mock_vector_factory, \
         patch('mem0.memory.storage.SQLiteManager') as mock_sqlite:

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedder_factory.return_value = mock_embedder

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = []
        mock_vector_store.add.return_value = None
        mock_vector_factory.return_value = mock_vector_store

        mock_sqlite.return_value = MagicMock()

        memory = Memory()
        memory.api_version = "v1.0"
        return memory, mock_llm, mock_vector_store


def create_mocked_async_memory():
    """Create a fully mocked AsyncMemory instance for testing."""
    with patch('mem0.utils.factory.LlmFactory.create') as mock_llm_factory, \
         patch('mem0.utils.factory.EmbedderFactory.create') as mock_embedder_factory, \
         patch('mem0.utils.factory.VectorStoreFactory.create') as mock_vector_factory, \
         patch('mem0.memory.storage.SQLiteManager') as mock_sqlite:

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
        mock_embedder_factory.return_value = mock_embedder

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = []
        mock_vector_store.add.return_value = None
        mock_vector_factory.return_value = mock_vector_store

        mock_sqlite.return_value = MagicMock()

        memory = AsyncMemory()
        memory.api_version = "v1.0"
        return memory, mock_llm, mock_vector_store


def test_thinking_tags_in_add_to_vector_store():
    """Test thinking tags handling in Memory._add_to_vector_store (sync)."""
    memory, mock_llm, mock_vector_store = create_mocked_memory()
    
    # Mock LLM responses for both phases
    mock_llm.generate_response.side_effect = [
        '        <think>Sync fact extraction</think>  \n{"facts": ["User loves sci-fi"]}',
        '        <think>Sync memory actions</think>  \n{"memory": [{"text": "Loves sci-fi", "event": "ADD"}]}'
    ]
    
    mock_vector_store.search.return_value = []
    
    result = memory._add_to_vector_store(
        messages=[{"role": "user", "content": "I love sci-fi movies"}],
        metadata={}, 
        filters={}, 
        infer=True
    )
    
    assert len(result) == 1
    assert result[0]["memory"] == "Loves sci-fi"
    assert result[0]["event"] == "ADD"



@pytest.mark.asyncio
async def test_async_thinking_tags_in_add_to_vector_store():
    """Test thinking tags handling in AsyncMemory._add_to_vector_store."""
    memory, mock_llm, mock_vector_store = create_mocked_async_memory()
    
    # Directly mock llm.generate_response instead of via asyncio.to_thread
    mock_llm.generate_response.side_effect = [
        '        <think>Async fact extraction</think>  \n{"facts": ["User loves sci-fi"]}',
        '        <think>Async memory actions</think>  \n{"memory": [{"text": "Loves sci-fi", "event": "ADD"}]}'
    ]
    
    # Mock asyncio.to_thread to call the function directly (bypass threading)
    async def mock_to_thread(func, *args, **kwargs):
        if func == mock_llm.generate_response:
            return func(*args, **kwargs)
        elif hasattr(func, '__name__') and 'embed' in func.__name__:
            return [0.1, 0.2, 0.3]
        elif hasattr(func, '__name__') and 'search' in func.__name__:
            return []
        else:
            return func(*args, **kwargs)
    
    with patch('mem0.memory.main.asyncio.to_thread', side_effect=mock_to_thread):
        result = await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I love sci-fi movies"}],
            metadata={}, 
            effective_filters={}, 
            infer=True
        )
    
    assert len(result) == 1
    assert result[0]["memory"] == "Loves sci-fi"
    assert result[0]["event"] == "ADD"

