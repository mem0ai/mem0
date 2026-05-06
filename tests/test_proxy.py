from unittest.mock import Mock, patch

import pytest

from mem0 import Memory, MemoryClient
from mem0.proxy.main import Chat, Completions, Mem0


@pytest.fixture
def mock_memory_client():
    mock_client = Mock(spec=MemoryClient)
    mock_client.user_email = None
    return mock_client


@pytest.fixture
def mock_openai_embedding_client():
    with patch("mem0.embeddings.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_openai_llm_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_litellm():
    with patch("mem0.proxy.main.litellm") as mock:
        yield mock


def test_mem0_initialization_with_api_key(mock_openai_embedding_client, mock_openai_llm_client):
    mem0 = Mem0()
    assert isinstance(mem0.mem0_client, Memory)
    assert isinstance(mem0.chat, Chat)


def test_mem0_initialization_with_config():
    config = {"some_config": "value"}
    with patch("mem0.Memory.from_config") as mock_from_config:
        mem0 = Mem0(config=config)
        mock_from_config.assert_called_once_with(config)
        assert isinstance(mem0.chat, Chat)


def test_mem0_initialization_without_params(mock_openai_embedding_client, mock_openai_llm_client):
    mem0 = Mem0()
    assert isinstance(mem0.mem0_client, Memory)
    assert isinstance(mem0.chat, Chat)


def test_chat_initialization(mock_memory_client):
    chat = Chat(mock_memory_client)
    assert isinstance(chat.completions, Completions)


def test_completions_create(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)

    messages = [{"role": "user", "content": "Hello, how are you?"}]
    mock_memory_client.search.return_value = {"results": [{"memory": "Some relevant memory"}]}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}
    mock_litellm.supports_function_calling.return_value = True

    response = completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user", temperature=0.7)

    mock_memory_client.add.assert_called_once()
    mock_memory_client.search.assert_called_once()
    # Verify search was called with filters dict, not top-level entity params
    search_call_kwargs = mock_memory_client.search.call_args[1]
    assert "filters" in search_call_kwargs
    assert search_call_kwargs["filters"]["user_id"] == "test_user"
    assert "user_id" not in search_call_kwargs or search_call_kwargs["user_id"] is None

    mock_litellm.completion.assert_called_once()
    call_args = mock_litellm.completion.call_args[1]
    assert call_args["model"] == "gpt-4.1-nano-2025-04-14"
    assert len(call_args["messages"]) == 2
    assert call_args["temperature"] == 0.7

    assert response == {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}


def test_completions_create_with_system_message(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]
    mock_memory_client.search.return_value = {"results": [{"memory": "Some relevant memory"}]}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user")

    call_args = mock_litellm.completion.call_args[1]
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][0]["content"] == "You are a helpful assistant."


def test_fetch_relevant_memories_with_entity_params(mock_memory_client):
    """Test that _fetch_relevant_memories passes entity params inside filters dict (BUG-024 fix)."""
    completions = Completions(mock_memory_client)
    messages = [{"role": "user", "content": "Hello"}]
    mock_memory_client.search.return_value = {"results": [{"memory": "User likes pizza"}]}

    completions._fetch_relevant_memories(
        messages=messages,
        user_id="alice",
        agent_id="bot_1",
        run_id=None,
        filters={"environment": "prod"},
        top_k=5,
    )

    # Verify search was called with filters containing all entity params
    search_call_kwargs = mock_memory_client.search.call_args[1]
    assert "filters" in search_call_kwargs
    assert search_call_kwargs["filters"]["user_id"] == "alice"
    assert search_call_kwargs["filters"]["agent_id"] == "bot_1"
    assert search_call_kwargs["filters"]["environment"] == "prod"
    # Verify entity params are NOT in top-level kwargs
    assert search_call_kwargs.get("user_id") is None
    assert search_call_kwargs.get("agent_id") is None


def test_format_query_with_memories_handles_dict_response(mock_memory_client):
    """Test that _format_query_with_memories handles dict response from MemoryClient (BUG-003 fix)."""
    completions = Completions(mock_memory_client)
    messages = [{"role": "user", "content": "What do I like?"}]

    # Simulate MemoryClient.search() response
    response = {"results": [{"memory": "User likes pizza", "id": "1"}, {"memory": "User is vegetarian", "id": "2"}]}

    result = completions._format_query_with_memories(messages, response)

    # Should successfully extract memories and format them
    assert "User likes pizza" in result
    assert "User is vegetarian" in result
    assert "Relevant Memories/Facts" in result
    assert "What do I like?" in result


def test_format_query_with_memories_handles_relations(mock_memory_client):
    """Test that _format_query_with_memories correctly extracts relations from response."""
    completions = Completions(mock_memory_client)
    messages = [{"role": "user", "content": "Tell me more"}]

    # Response with both results and relations
    response = {
        "results": [{"memory": "User likes pizza", "id": "1"}],
        "relations": [{"source": "User", "relationship": "likes", "target": "pizza"}],
    }

    result = completions._format_query_with_memories(messages, response)

    # Should include memories and entities/relations
    assert "User likes pizza" in result
    assert "pizza" in result  # from entities
    assert "Entities:" in result
