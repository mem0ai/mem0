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
    # MemoryClient.search() returns {"results": [...]}, not a bare list.
    mock_memory_client.search.return_value = {"results": [{"memory": "Some relevant memory"}]}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}
    mock_litellm.supports_function_calling.return_value = True

    response = completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user", temperature=0.7)

    mock_memory_client.add.assert_called_once()
    mock_memory_client.search.assert_called_once()

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


# ---------------------------------------------------------------------------
# /search call shape: entity ids must go inside `filters`, not as top-level
# kwargs. Both Memory.search() and MemoryClient.search() reject the latter.
# ---------------------------------------------------------------------------

def test_search_entity_ids_go_into_filters(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        agent_id="a1",
        run_id="r1",
    )

    _, kwargs = mock_memory_client.search.call_args
    assert "user_id" not in kwargs
    assert "agent_id" not in kwargs
    assert "run_id" not in kwargs
    assert kwargs["filters"] == {"user_id": "u1", "agent_id": "a1", "run_id": "r1"}


def test_search_caller_filters_preserved_alongside_entity_ids(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        filters={"category": "food"},
    )

    _, kwargs = mock_memory_client.search.call_args
    assert kwargs["filters"] == {"category": "food", "user_id": "u1"}


def test_search_caller_filters_take_precedence_over_top_level_entity(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "hi"}],
        user_id="top-level-u",
        filters={"user_id": "filters-u"},
    )

    _, kwargs = mock_memory_client.search.call_args
    assert kwargs["filters"] == {"user_id": "filters-u"}


# ---------------------------------------------------------------------------
# MemoryClient branch must iterate `relevant_memories["results"]`, not the
# dict directly (which yields keys, raising TypeError on memory["memory"]).
# ---------------------------------------------------------------------------

def test_memoryclient_branch_iterates_results_key(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {
        "results": [
            {"memory": "User likes teal"},
            {"memory": "User lives in Santa Cruz"},
        ]
    }
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "What do I like?"}],
        user_id="u1",
    )

    # The system prompt + augmented user prompt are passed to litellm. The
    # augmented prompt must include the memories' text — proves the proxy
    # successfully iterated `relevant_memories["results"]`.
    call_args = mock_litellm.completion.call_args[1]
    augmented_user = call_args["messages"][-1]["content"]
    assert "User likes teal" in augmented_user
    assert "User lives in Santa Cruz" in augmented_user
