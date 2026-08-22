import builtins
import importlib
import inspect
import sys
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


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "user", "content": "original"}],
        [{"role": "system", "content": "system"}, {"role": "user", "content": "original"}],
    ],
    ids=["no_system_message", "with_system_message"],
)
def test_prepare_messages_does_not_alias_caller_messages(mock_memory_client, messages):
    """`_prepare_messages` must hand back dicts the caller does not own.

    Both branches used to alias: without a system message it built a new outer
    list out of the caller's dicts, and with one it returned the caller's list
    itself. Either way, `create()`'s later write to
    `prepared_messages[-1]["content"]` landed in the caller's own message.
    """
    prepared = Completions(mock_memory_client)._prepare_messages(messages)

    prepared[-1]["content"] = "injected"

    assert messages[-1]["content"] == "original"


def test_completions_create_does_not_mutate_caller_messages(mock_memory_client, mock_litellm):
    """Enriching the LLM request must not rewrite the caller's conversation.

    `create()` replaces the last message's content with the retrieved-memories
    prompt before calling litellm, while `_async_add_to_memory` hands the
    caller's list to a background thread. When those two shared dicts, the
    caller saw its input rewritten and — depending on which side of the race
    the thread landed on — the memory write could persist the generated
    "Relevant Memories/Facts" block as new user content.

    Asserting the caller's list is untouched after `create()` returns covers the
    background write too: that thread is given this same list, so if it is never
    mutated there is no interleaving in which the thread can observe the
    injected prompt.
    """
    completions = Completions(mock_memory_client)

    messages = [{"role": "user", "content": "What should I cook tonight?"}]
    mock_memory_client.search.return_value = [{"memory": "User is allergic to peanuts"}]
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user")

    assert messages == [{"role": "user", "content": "What should I cook tonight?"}]

    # The enrichment still has to reach the model — this is not a fix that just
    # stops writing anywhere.
    sent = mock_litellm.completion.call_args[1]["messages"]
    assert "User is allergic to peanuts" in sent[-1]["content"]
    assert "What should I cook tonight?" in sent[-1]["content"]


def test_async_add_to_memory_receives_the_unenriched_messages(mock_memory_client, mock_litellm):
    """The background memory write must see the user's text, not the enriched prompt.

    `create()` hands `_async_add_to_memory` the caller's list and only afterwards
    writes the retrieved-memories prompt into the prepared copy. Pinning that
    argument keeps a later refactor from passing `prepared_messages` instead, which
    would persist the generated "Relevant Memories/Facts" block as new user content.
    """
    completions = Completions(mock_memory_client)

    messages = [{"role": "user", "content": "What should I cook tonight?"}]
    mock_memory_client.search.return_value = [{"memory": "User is allergic to peanuts"}]
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    with patch.object(Completions, "_async_add_to_memory") as add_to_memory:
        completions.create(model="gpt-4.1-nano-2025-04-14", messages=messages, user_id="test_user")

    stored_messages = add_to_memory.call_args[0][0]
    assert stored_messages[-1]["content"] == "What should I cook tonight?"


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


def test_missing_litellm_raises_actionable_import_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "mem0.proxy.main", raising=False)
    monkeypatch.delitem(sys.modules, "litellm", raising=False)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "litellm":
            raise ImportError("No module named 'litellm'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match="pip install litellm"):
        importlib.import_module("mem0.proxy.main")
