"""Tests for the Mem0MemoryStore (Strands MemoryStore integration).

The store is exercised with a mocked Mem0ServiceClient, so no live Mem0 server
(or the ``mem0ai`` SDK) is required.
"""

from unittest.mock import MagicMock

import pytest
from strands.memory import MemoryEntry, MemoryStore
from strands.memory.types import _has_method, _has_write_sink

from mem0_strands import Mem0MemoryStore


@pytest.fixture
def mock_client():
    """A mocked Mem0ServiceClient."""
    return MagicMock()


def make_store(mock_client, **kwargs):
    """Build a store wired to the mocked client (default scope: user_id=alex)."""
    kwargs.setdefault("user_id", "alex")
    return Mem0MemoryStore(client=mock_client, **kwargs)


# ---------------------------------------------------------------------------
# Construction / protocol conformance
# ---------------------------------------------------------------------------


def test_requires_a_scope():
    """At least one of user_id / agent_id / run_id / app_id is mandatory."""
    with pytest.raises(ValueError, match="at least one of"):
        Mem0MemoryStore()


def test_app_id_with_oss_config_rejected_at_construction():
    """app_id is platform-only; pairing it with an OSS config fails at construction."""
    with pytest.raises(ValueError, match="platform-only"):
        Mem0MemoryStore(app_id="app1", config={"vector_store": {"provider": "qdrant"}})


def test_scope_collects_only_set_fields(mock_client):
    """Only the provided entity fields end up in the scope."""
    store = Mem0MemoryStore(client=mock_client, user_id="alex", agent_id="assistant")
    assert store.scope == {"user_id": "alex", "agent_id": "assistant"}


def test_is_a_memory_store(mock_client):
    """The store is a genuine MemoryStore subclass (MemoryStore is a
    non-runtime-checkable Protocol, so check the MRO rather than isinstance)."""
    store = make_store(mock_client)
    assert MemoryStore in type(store).__mro__


def test_protocol_attributes_default(mock_client):
    """Protocol attributes take sensible, writable-by-default values."""
    store = make_store(mock_client)
    assert store.name == "mem0"
    assert store.description is not None
    assert store.max_search_results is None
    assert store.writable is True
    assert store.extraction is None
    assert store.scope == {"user_id": "alex"}


def test_protocol_attributes_override(mock_client):
    """Config fields are honored."""
    store = make_store(
        mock_client,
        name="notes",
        description="d",
        max_search_results=3,
        writable=False,
        extraction=True,
        metadata={"team": "growth"},
    )
    assert store.name == "notes"
    assert store.max_search_results == 3
    assert store.writable is False
    assert store.extraction is True
    assert store.metadata == {"team": "growth"}


def test_write_sink_detection(mock_client):
    """Both `add` and `add_messages` are real sinks -- extraction defaults to
    Mem0's server-side path (add_messages), not a client-side ModelExtractor."""
    store = make_store(mock_client)
    assert _has_method(store, "search") is True
    assert _has_method(store, "add") is True
    assert _has_method(store, "add_messages") is True
    assert _has_method(store, "initialize") is False
    assert _has_method(store, "get_tools") is False
    assert _has_write_sink(store) is True


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


async def test_search_maps_to_memory_entries(mock_client):
    """Mem0 hits are mapped to MemoryEntry with metadata preserved."""
    mock_client.search_memories.return_value = [
        {
            "id": "mem-1",
            "memory": "Alex prefers dark roast",
            "score": 0.91,
            "categories": ["preferences"],
            "created_at": "2026-07-02T00:00:00Z",
            "user_id": "alex",
            "metadata": {"category": "prefs"},
        }
    ]
    store = make_store(mock_client)

    results = await store.search("coffee")

    assert len(results) == 1
    entry = results[0]
    assert isinstance(entry, MemoryEntry)
    assert entry.content == "Alex prefers dark roast"
    assert entry.metadata["id"] == "mem-1"
    assert entry.metadata["score"] == 0.91
    assert entry.metadata["categories"] == ["preferences"]
    assert entry.metadata["category"] == "prefs"


async def test_search_default_top_k(mock_client):
    """With no options and no configured max, the default top_k is used."""
    mock_client.search_memories.return_value = []
    store = make_store(mock_client)

    await store.search("q")

    mock_client.search_memories.assert_called_once_with("q", {"user_id": "alex"}, 5)


async def test_search_options_override_top_k(mock_client):
    """SearchOptions.max_search_results wins over the configured default."""
    mock_client.search_memories.return_value = []
    store = make_store(mock_client, max_search_results=3)

    await store.search("q", {"max_search_results": 10})

    mock_client.search_memories.assert_called_once_with("q", {"user_id": "alex"}, 10)


async def test_search_config_top_k(mock_client):
    """The configured max is used when options omit it."""
    mock_client.search_memories.return_value = []
    store = make_store(mock_client, max_search_results=7)

    await store.search("q")

    mock_client.search_memories.assert_called_once_with("q", {"user_id": "alex"}, 7)


async def test_search_handles_missing_content(mock_client):
    """A hit without memory text maps to an empty string, not None."""
    mock_client.search_memories.return_value = [{"id": "mem-2"}]
    store = make_store(mock_client)

    results = await store.search("q")

    assert results[0].content == ""
    assert results[0].metadata == {"id": "mem-2"}


# ---------------------------------------------------------------------------
# add / add_messages
# ---------------------------------------------------------------------------


async def test_add_writes_a_verbatim_fact(mock_client):
    """add() forwards content, scope and merged metadata to store_memory."""
    stored = {"id": "mem-9"}
    mock_client.store_memory.return_value = stored
    store = make_store(mock_client, metadata={"team": "growth"})

    result = await store.add("new fact", {"source": "chat"})

    assert result == stored
    mock_client.store_memory.assert_called_once_with(
        "new fact", {"user_id": "alex"}, {"team": "growth", "source": "chat"}
    )


async def test_add_without_metadata_uses_store_default(mock_client):
    """With no per-call metadata, the store's default metadata is used."""
    store = make_store(mock_client, metadata={"team": "growth"})

    await store.add("fact")

    mock_client.store_memory.assert_called_once_with("fact", {"user_id": "alex"}, {"team": "growth"})


async def test_add_messages_renders_content_blocks(mock_client):
    """add_messages renders Strands content blocks to text before sending.

    Strands hands content as list[ContentBlock] (a text block is ``{"text": ...}``);
    mem0 keeps only text parts, so the store must flatten each turn to a string.
    """
    messages = [
        {"role": "user", "content": [{"text": "I love hiking"}]},
        {"role": "assistant", "content": [{"text": "Noted!"}]},
    ]
    store = make_store(mock_client)

    await store.add_messages(messages)

    mock_client.store_messages.assert_called_once_with(
        [{"role": "user", "content": "I love hiking"}, {"role": "assistant", "content": "Noted!"}],
        {"user_id": "alex"},
    )


async def test_add_messages_skips_empty_turns(mock_client):
    """A turn with no text (a pure tool-use turn) renders to nothing and is not sent."""
    store = make_store(mock_client)

    result = await store.add_messages([{"role": "assistant", "content": [{"toolUse": {"name": "x"}}]}])

    assert result is None
    mock_client.store_messages.assert_not_called()


# ---------------------------------------------------------------------------
# lazy client construction
# ---------------------------------------------------------------------------


def test_client_constructed_lazily(monkeypatch):
    """No Mem0ServiceClient is built until the client property is accessed."""
    calls = {"n": 0}

    class FakeClient:
        def __init__(self, api_key=None, host=None, config=None, client=None):
            calls["n"] += 1
            self.api_key = api_key

    monkeypatch.setattr("mem0_strands.store.Mem0ServiceClient", FakeClient)

    store = Mem0MemoryStore(user_id="alex", api_key="m0-x")
    assert calls["n"] == 0  # not built yet

    client = store.client
    assert calls["n"] == 1
    assert client.api_key == "m0-x"

    # Second access reuses the same instance.
    assert store.client is client
    assert calls["n"] == 1
