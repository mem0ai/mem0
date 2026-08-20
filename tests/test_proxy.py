import inspect
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
    mock_memory_client.search.return_value = [{"memory": "Some relevant memory"}]
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
    mock_memory_client.search.return_value = [{"memory": "Some relevant memory"}]
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "I'm doing well, thank you!"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user")

    call_args = mock_litellm.completion.call_args[1]
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][0]["content"] == "You are a helpful assistant."


def test_completions_create_messages_default_does_not_leak_between_calls(mock_memory_client, mock_litellm):
    """Regression test for the B006 mutable-default bug in Completions.create.

    Before the fix, `messages: List = []` made every call that didn't pass
    `messages` share the same module-level list. A previous call could mutate
    that list (e.g. via `_prepare_messages`) and subsequent calls would observe
    the leaked state instead of an empty list.

    After the fix, `messages` defaults to `None` and is normalized to a fresh
    `[]` inside the function on each call, isolating call N from call N-1.
    """
    completions = Completions(mock_memory_client)
    mock_litellm.supports_function_calling.return_value = True
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_memory_client.search.return_value = []

    # Each call passes a fresh list — confirms the public happy path stays green.
    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "first"}],
        user_id="user_a",
    )
    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "second"}],
        user_id="user_b",
    )

    # The Completions.create signature must not bind a mutable container as
    # the default for `messages`. This is what B006 lints against and what the
    # historical default `messages: List = []` violated.
    sig = inspect.signature(Completions.create)
    messages_default = sig.parameters["messages"].default
    assert messages_default is None, (
        f"Completions.create(messages=...) must default to None to avoid the "
        f"B006 shared-default-list bug; got {messages_default!r}."
    )


def test_async_add_to_memory_does_not_pass_filters_to_oss_memory():
    oss_memory = Mock(spec=Memory)
    completions = Completions(oss_memory)

    completions._async_add_to_memory(
        messages=[{"role": "user", "content": "hi"}],
        user_id="alice",
        agent_id=None,
        run_id=None,
        metadata=None,
        filters={"category": "food"},
    )
    for _ in range(50):
        if oss_memory.add.called:
            break
        import time

        time.sleep(0.01)

    oss_memory.add.assert_called_once()
    assert "filters" not in oss_memory.add.call_args.kwargs


def test_async_add_to_memory_forwards_filters_to_memory_client():
    client = Mock(spec=MemoryClient)
    completions = Completions(client)

    completions._async_add_to_memory(
        messages=[{"role": "user", "content": "hi"}],
        user_id="alice",
        agent_id=None,
        run_id=None,
        metadata=None,
        filters={"category": "food"},
    )
    for _ in range(50):
        if client.add.called:
            break
        import time

        time.sleep(0.01)

    client.add.assert_called_once()
    assert client.add.call_args.kwargs["filters"] == {"category": "food"}


def test_async_add_to_memory_logs_background_failures(caplog):
    oss_memory = Mock(spec=Memory)
    oss_memory.add.side_effect = TypeError("boom")
    completions = Completions(oss_memory)

    with caplog.at_level("ERROR"):
        completions._async_add_to_memory(
            messages=[{"role": "user", "content": "hi"}],
            user_id="alice",
            agent_id=None,
            run_id=None,
            metadata=None,
            filters=None,
        )
        for _ in range(50):
            if "Failed to add memory asynchronously" in caplog.text:
                break
            import time

            time.sleep(0.01)

    assert "Failed to add memory asynchronously" in caplog.text
