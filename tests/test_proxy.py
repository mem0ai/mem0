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

    response = completions.create(
        model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user", temperature=0.7
    )

    mock_memory_client.add.assert_called_once()
    mock_memory_client.search.assert_called_once()

    mock_litellm.completion.assert_called_once()
    call_args = mock_litellm.completion.call_args[1]
    assert call_args["model"] == "gpt-4.1-nano-2025-04-14"
    assert len(call_args["messages"]) == 2
    assert call_args["temperature"] == 0.7

    assert response == {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}


def test_fetch_relevant_memories_passes_entity_ids_in_filters(mock_memory_client):
    """_fetch_relevant_memories must pass user_id/agent_id/run_id inside filters={}
    not as top-level kwargs — regression test for #4907 Bug 1.

    Both Memory.search() and MemoryClient.search() now reject top-level entity
    params with ValueError. Passing them inside filters avoids this.
    """
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}

    completions._fetch_relevant_memories(
        messages=[{"role": "user", "content": "Hi"}],
        user_id="u1",
        agent_id="a1",
        run_id="r1",
        filters=None,
        top_k=5,
    )

    call_kwargs = mock_memory_client.search.call_args[1]
    assert "user_id" not in call_kwargs, "user_id must not be a top-level kwarg"
    assert "agent_id" not in call_kwargs, "agent_id must not be a top-level kwarg"
    assert "run_id" not in call_kwargs, "run_id must not be a top-level kwarg"
    assert call_kwargs["filters"]["user_id"] == "u1"
    assert call_kwargs["filters"]["agent_id"] == "a1"
    assert call_kwargs["filters"]["run_id"] == "r1"


def test_format_query_with_memories_iterates_results_for_memory_client(mock_memory_client):
    """_format_query_with_memories must index relevant_memories['results'] for MemoryClient,
    not iterate the dict directly — regression test for #4907 Bug 2.

    MemoryClient.search() returns {'results': [...], ...}. The old code iterated
    the dict itself (yielding string keys like 'results', 'relations') and crashed
    with: TypeError: string indices must be integers, not 'str'
    """
    completions = Completions(mock_memory_client)
    relevant_memories = {"results": [{"memory": "I like hiking"}, {"memory": "I dislike coffee"}]}
    messages = [{"role": "user", "content": "What do I like?"}]

    result = completions._format_query_with_memories(messages, relevant_memories)

    assert "I like hiking" in result
    assert "I dislike coffee" in result
    assert "What do I like?" in result


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
