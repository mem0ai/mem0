"""Tests for Mem0ServiceClient -- the platform/OSS routing and response shaping.

Both backends are faked, so no ``mem0ai`` SDK or live server is required.
"""

from strands_mem0.client import Mem0ServiceClient, _extract_results, _is_platform_client


class FakeMemoryClient:
    """Stand-in for mem0.MemoryClient (platform: scope goes through `filters`)."""

    def __init__(self):
        self.add_calls = []
        self.search_calls = []

    def add(self, messages, **kwargs):
        self.add_calls.append((messages, kwargs))
        return {"results": [{"id": "m1"}]}

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return {"results": [{"id": "m1", "memory": "hi"}]}


class FakeMemory:
    """Stand-in for mem0.Memory (OSS: scope goes as top-level kwargs)."""

    def __init__(self):
        self.search_calls = []

    def add(self, messages, **kwargs):
        return {"results": []}

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return {"results": []}


def platform_client():
    """A Mem0ServiceClient wrapping a fake platform client."""
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    client = Mem0ServiceClient(client=fake)
    return client, fake


# ---------------------------------------------------------------------------
# backend detection
# ---------------------------------------------------------------------------


def test_detects_platform_by_class_name():
    assert _is_platform_client(FakeMemory()) is False  # not named MemoryClient
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    assert _is_platform_client(fake) is True


def test_injected_client_sets_platform_flag():
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    assert Mem0ServiceClient(client=fake).is_platform is True
    assert Mem0ServiceClient(client=FakeMemory()).is_platform is False


# ---------------------------------------------------------------------------
# write routing
# ---------------------------------------------------------------------------


def test_store_memory_is_verbatim():
    """store_memory writes with infer=False and scope as top-level kwargs."""
    client, fake = platform_client()

    client.store_memory("a fact", {"user_id": "alex"}, {"k": "v"})

    messages, kwargs = fake.add_calls[0]
    assert messages == "a fact"
    assert kwargs["infer"] is False
    assert kwargs["user_id"] == "alex"
    assert kwargs["metadata"] == {"k": "v"}


def test_store_messages_infers():
    """store_messages hands raw turns to Mem0 with infer=True."""
    client, fake = platform_client()

    turns = [{"role": "user", "content": "hi"}]
    client.store_messages(turns, {"user_id": "alex"})

    messages, kwargs = fake.add_calls[0]
    assert messages == turns
    assert kwargs["infer"] is True
    assert kwargs["user_id"] == "alex"


# ---------------------------------------------------------------------------
# search routing (the platform/OSS asymmetry)
# ---------------------------------------------------------------------------


def test_platform_search_uses_filters():
    """Platform search passes scope inside `filters`, never top-level."""
    client, fake = platform_client()

    client.search_memories("q", {"user_id": "alex"}, 5)

    _, kwargs = fake.search_calls[0]
    assert kwargs["filters"] == {"user_id": "alex"}
    assert kwargs["top_k"] == 5
    assert "user_id" not in kwargs  # would be rejected by the platform client


def test_oss_search_uses_top_level_scope():
    """OSS search passes scope as top-level kwargs with `limit`."""
    fake = FakeMemory()
    client = Mem0ServiceClient(client=fake)

    client.search_memories("q", {"user_id": "alex"}, 5)

    _, kwargs = fake.search_calls[0]
    assert kwargs["user_id"] == "alex"
    assert kwargs["limit"] == 5
    assert "filters" not in kwargs


# ---------------------------------------------------------------------------
# response normalization
# ---------------------------------------------------------------------------


def test_extract_results_shapes():
    assert _extract_results({"results": [{"id": 1}]}) == [{"id": 1}]
    assert _extract_results([{"id": 1}]) == [{"id": 1}]
    assert _extract_results({"nope": 1}) == []
    assert _extract_results(None) == []
