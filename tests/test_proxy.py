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


def test_completions_create_keeps_filters_out_of_add(mock_memory_client, mock_litellm):
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}
    mock_litellm.supports_function_calling.return_value = True

    with patch("mem0.proxy.main.threading.Thread") as mock_thread:
        mock_thread.side_effect = lambda target, daemon: Mock(start=target)
        completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[{"role": "user", "content": "Hello"}],
            user_id="test_user",
            filters={"categories": {"in": ["travel"]}},
        )

    assert "filters" not in mock_memory_client.add.call_args.kwargs
    assert mock_memory_client.add.call_args.kwargs["user_id"] == "test_user"
    # Entity ids route through filters (merged with the user-supplied filters),
    # matching the search() contract that rejects top-level entity params.
    assert mock_memory_client.search.call_args.kwargs["filters"] == {
        "categories": {"in": ["travel"]},
        "user_id": "test_user",
    }


def test_completions_search_routes_entity_ids_through_filters(mock_memory_client, mock_litellm):
    """Regression test: chat completions must route entity ids through filters.

    `Memory.search` and `MemoryClient.search` reject top-level entity params
    (`user_id`/`agent_id`/`run_id`) with a ValueError — they must be passed via
    `filters={"user_id": ...}` instead. The proxy's `_fetch_relevant_memories`
    used to pass them as top-level kwargs, so every chat completion whose last
    message is a user message raised:

        ValueError: Top-level entity parameters {'user_id'} are not supported
        in search(). Use filters={'user_id': '...'} instead.

    The search must therefore be called with the entity ids merged into
    `filters` (user-supplied filters preserved, None entity ids omitted) and no
    top-level entity kwargs at all.
    """
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": [{"memory": "Some relevant memory"}]}
    mock_litellm.supports_function_calling.return_value = True

    with patch("mem0.proxy.main.threading.Thread") as mock_thread:
        mock_thread.side_effect = lambda target, daemon: Mock(start=target)
        completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[{"role": "user", "content": "Hello"}],
            user_id="test_user",
            filters={"categories": {"in": ["travel"]}},
        )

    search_kwargs = mock_memory_client.search.call_args.kwargs
    # No top-level entity params — this is what both search() implementations reject.
    assert "user_id" not in search_kwargs
    assert "agent_id" not in search_kwargs
    assert "run_id" not in search_kwargs
    # Entity ids live in filters, merged with the user-supplied filters.
    assert search_kwargs["filters"]["user_id"] == "test_user"
    assert search_kwargs["filters"]["categories"] == {"in": ["travel"]}


def test_completions_search_filters_omit_unset_entity_ids(mock_memory_client, mock_litellm):
    """Only the entity ids actually provided should land in filters."""
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": []}
    mock_litellm.supports_function_calling.return_value = True

    with patch("mem0.proxy.main.threading.Thread") as mock_thread:
        mock_thread.side_effect = lambda target, daemon: Mock(start=target)
        completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[{"role": "user", "content": "Hello"}],
            user_id="test_user",
        )

    search_kwargs = mock_memory_client.search.call_args.kwargs
    assert "user_id" not in search_kwargs
    assert search_kwargs["filters"] == {"user_id": "test_user"}


def test_completions_format_query_reads_results_key_for_memory_client(mock_memory_client, mock_litellm):
    """Regression test: the MemoryClient branch of _format_query_with_memories
    must read `relevant_memories["results"]`, not iterate the response dict.

    MemoryClient.search returns {"results": [...]}; iterating the dict yields
    the key string "results", and `memory["memory"]` on that string raises
    TypeError: string indices must be integers.
    """
    completions = Completions(mock_memory_client)
    mock_memory_client.search.return_value = {"results": [{"memory": "user likes cats"}]}
    mock_litellm.completion.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_litellm.supports_function_calling.return_value = True

    response = completions.create(
        model="gpt-4.1-nano-2025-04-14",
        messages=[{"role": "user", "content": "Hello"}],
        user_id="test_user",
    )

    assert response == {"choices": [{"message": {"content": "ok"}}]}
    prompt = mock_litellm.completion.call_args[1]["messages"][-1]["content"]
    assert "user likes cats" in prompt


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
    mock_memory_client.search.return_value = {"results": []}

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
