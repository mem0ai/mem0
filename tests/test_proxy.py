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


def test_fetch_relevant_memories_passes_entities_via_filters(mock_memory_client):
    """Regression for #4907 bug 1: top-level entity params must be wrapped in filters."""
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}

    completions._fetch_relevant_memories(
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        agent_id="a1",
        run_id=None,
        filters=None,
        top_k=5,
    )

    call_kwargs = mock_memory_client.search.call_args.kwargs
    # The buggy code passed user_id/agent_id/run_id as top-level kwargs which
    # both Memory.search and MemoryClient.search now reject.
    assert "user_id" not in call_kwargs
    assert "agent_id" not in call_kwargs
    assert "run_id" not in call_kwargs
    # They must be inside filters instead.
    assert call_kwargs["filters"] == {"user_id": "u1", "agent_id": "a1"}
    assert call_kwargs["top_k"] == 5


def test_fetch_relevant_memories_preserves_caller_filters(mock_memory_client):
    """User-supplied filters must merge with entity ids, not be clobbered."""
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}

    completions._fetch_relevant_memories(
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        agent_id=None,
        run_id=None,
        filters={"category": "work", "user_id": "explicit"},
        top_k=10,
    )

    filters = mock_memory_client.search.call_args.kwargs["filters"]
    # Caller-provided user_id wins over the param (don't silently overwrite).
    assert filters["user_id"] == "explicit"
    assert filters["category"] == "work"


def test_format_query_with_memoryclient_uses_results_key(mock_memory_client):
    """Regression for #4907 bug 2: MemoryClient.search returns {'results': [...]}."""
    completions = Completions(mock_memory_client)

    relevant = {"results": [{"memory": "fact one"}, {"memory": "fact two"}]}
    out = completions._format_query_with_memories(
        messages=[{"role": "user", "content": "Q?"}],
        relevant_memories=relevant,
    )

    # Should contain both memory strings (proves we iterated results, not dict keys).
    assert "fact one" in out
    assert "fact two" in out
    assert "Q?" in out


def test_format_query_handles_empty_results(mock_memory_client):
    """Empty result set must produce a valid prompt, not crash."""
    completions = Completions(mock_memory_client)

    out = completions._format_query_with_memories(
        messages=[{"role": "user", "content": "Q?"}],
        relevant_memories={"results": []},
    )
    assert "Relevant Memories/Facts: " in out
    assert "Q?" in out
