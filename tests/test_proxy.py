import inspect
import logging
from unittest.mock import Mock, create_autospec, patch

import pytest

from mem0 import Memory, MemoryClient
from mem0.proxy.main import Chat, Completions, Mem0


class _ImmediateThread:
    """Stand-in for threading.Thread that runs the target inline.

    _async_add_to_memory fires a daemon thread and never returns a handle, so
    without this the write is unobservable from a test.
    """

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture
def run_threads_inline():
    with patch("mem0.proxy.main.threading.Thread", _ImmediateThread):
        yield


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


# --- proxy write path -------------------------------------------------------
#
# Regression tests: _async_add_to_memory used to pass `filters=` unconditionally.
# OSS Memory.add() has no such parameter, so every proxy write died with
# TypeError inside an unobserved daemon thread while create() still returned a
# normal completion.

MESSAGES = [{"role": "user", "content": "I'm vegetarian and allergic to nuts."}]


def test_oss_add_does_not_receive_filters(run_threads_inline):
    """autospec enforces the real Memory.add signature, so the old call raises."""
    oss_client = create_autospec(Memory, instance=True)
    completions = Completions(oss_client)

    completions._async_add_to_memory(MESSAGES, "alice", None, None, None, None)

    oss_client.add.assert_called_once()
    assert "filters" not in oss_client.add.call_args.kwargs
    assert oss_client.add.call_args.kwargs["user_id"] == "alice"


def test_oss_add_call_binds_against_the_real_memory_add_signature(run_threads_inline):
    """The strongest pin: whatever the proxy sends must bind to Memory.add for
    real, independent of how the client is mocked."""
    oss_client = create_autospec(Memory, instance=True)
    Completions(oss_client)._async_add_to_memory(MESSAGES, "alice", None, None, None, None)

    sent = oss_client.add.call_args.kwargs
    inspect.signature(Memory.add).bind(Mock(), **sent)  # must not raise

    # And the historical call shape must still be rejected, so this test fails
    # loudly if `filters` is ever reintroduced on the OSS path.
    with pytest.raises(TypeError):
        inspect.signature(Memory.add).bind(Mock(), **sent, filters=None)


def test_platform_add_still_receives_filters(run_threads_inline):
    """filters is a documented Platform add() option (AddMemoryOptions), so the
    fix must not strip it from MemoryClient."""
    platform_client = Mock(spec=MemoryClient)
    completions = Completions(platform_client)
    filters = {"AND": [{"user_id": "alice"}]}

    completions._async_add_to_memory(MESSAGES, "alice", None, None, None, filters)

    assert platform_client.add.call_args.kwargs["filters"] == filters


def test_oss_filters_are_reported_not_silently_dropped(run_threads_inline, caplog):
    oss_client = create_autospec(Memory, instance=True)
    completions = Completions(oss_client)

    with caplog.at_level(logging.WARNING, logger="mem0.proxy.main"):
        completions._async_add_to_memory(MESSAGES, "alice", None, None, None, {"a": 1})

    assert "filters" in caplog.text
    assert "filters" not in oss_client.add.call_args.kwargs


def test_background_add_failure_is_logged_not_swallowed(run_threads_inline, caplog):
    """create() returns a normal completion either way, so a failed write has to
    leave a trace somewhere the user can find."""
    oss_client = create_autospec(Memory, instance=True)
    oss_client.add.side_effect = RuntimeError("vector store unreachable")
    completions = Completions(oss_client)

    with caplog.at_level(logging.ERROR, logger="mem0.proxy.main"):
        completions._async_add_to_memory(MESSAGES, "alice", None, None, None, None)

    assert "Failed to add conversation to memory" in caplog.text
    assert "vector store unreachable" in caplog.text
