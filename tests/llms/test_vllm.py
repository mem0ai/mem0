from unittest.mock import MagicMock, Mock, patch

import pytest

from mem0 import AsyncMemory, Memory
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.vllm import VllmLLM


@pytest.fixture
def mock_vllm_client():
    with patch("mem0.llms.vllm.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_vllm_client):
    config = BaseLlmConfig(model="Qwen/Qwen2.5-32B-Instruct", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = VllmLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_vllm_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_vllm_client.chat.completions.create.assert_called_once_with(
        model="Qwen/Qwen2.5-32B-Instruct", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_vllm_client):
    config = BaseLlmConfig(model="Qwen/Qwen2.5-32B-Instruct", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = VllmLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Add a new memory: Today is a sunny day."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_memory",
                "description": "Add a memory",
                "parameters": {
                    "type": "object",
                    "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
                    "required": ["data"],
                },
            },
        }
    ]

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "I've added the memory for you."

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "Today is a sunny day."}'

    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_vllm_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_vllm_client.chat.completions.create.assert_called_once_with(
        model="Qwen/Qwen2.5-32B-Instruct",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        tools=tools,
        tool_choice="auto",
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}



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


def test_thinking_tags_sync():
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
async def test_async_thinking_tags_async():
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