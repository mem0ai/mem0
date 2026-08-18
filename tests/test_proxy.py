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


# ---------------------------------------------------------------------------
# Regression tests: caller-owned message dicts must not be mutated
# ---------------------------------------------------------------------------


def test_prepare_messages_does_not_alias_dicts_without_system_message(mock_memory_client):
    """_prepare_messages() must return isolated dict copies when the caller has
    no system message. Mutating the prepared list must NOT touch the originals."""
    completions = Completions(mock_memory_client)

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "original"},
    ]

    # Temporarily remove the system message to exercise the prepend-system path.
    user_only = [{"role": "user", "content": "original"}]
    prepared = completions._prepare_messages(user_only)

    # Mutate the prepared copy.
    prepared[-1]["content"] = "MUTATED"

    # The caller's dict must be untouched.
    assert user_only[-1]["content"] == "original", (
        "_prepare_messages() aliased the caller's dict (no-system-message path)"
    )


def test_prepare_messages_does_not_alias_dicts_with_system_message(mock_memory_client):
    """_prepare_messages() must return isolated dict copies even when the caller
    already provides a system message. This is the path that previously returned
    the original list unchanged, leaving the dicts shared."""
    completions = Completions(mock_memory_client)

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "original"},
    ]

    prepared = completions._prepare_messages(messages)

    # Mutating the prepared copy must NOT bleed back to the caller's dicts.
    prepared[-1]["content"] = "MUTATED"

    assert messages[-1]["content"] == "original", (
        "_prepare_messages() aliased the caller's dict (with-system-message path)"
    )


def test_create_does_not_mutate_caller_messages(mock_memory_client, mock_litellm):
    """create() must not mutate the caller-owned messages list or any of its
    nested dicts, even after memory-enrichment replaces the last user content."""
    completions = Completions(mock_memory_client)

    original_content = "original user question"
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": original_content},
    ]

    # Capture what _async_add_to_memory receives so we can verify it sees the
    # original content and not the enriched prompt.
    captured_add_messages = []

    def fake_add(messages, **kwargs):
        # Record a snapshot of the content at call time.
        captured_add_messages.extend([dict(m) for m in messages])

    mock_memory_client.add.side_effect = fake_add
    mock_memory_client.search.return_value = [{"memory": "some fact"}]
    mock_litellm.supports_function_calling.return_value = True
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "reply"}}]}

    completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=messages,
        user_id="test_user",
    )

    # 1. The caller's list structure must be intact.
    assert len(messages) == 2

    # 2. The caller's last user dict must NOT have been overwritten.
    assert messages[-1]["content"] == original_content, (
        "create() mutated the caller's last user message content"
    )

    # 3. The memory write must have received the original question, not the
    #    enriched prompt that contains "Relevant Memories/Facts".
    # (The background thread runs synchronously via mock side_effect here.)
    for msg in captured_add_messages:
        assert "Relevant Memories/Facts" not in msg.get("content", ""), (
            "_async_add_to_memory received the enriched prompt instead of the original message"
        )
