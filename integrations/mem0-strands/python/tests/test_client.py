"""Tests for Mem0ServiceClient: backend routing, call shapes, and response shaping.

The fakes mirror the *real* mem0ai signatures: a keyword-only ``search`` that
rejects top-level entity params, and a fixed-signature OSS ``add`` with no
``**kwargs``. So a call shape the real SDK would reject fails here too, which is
what the earlier permissive fakes did not do.
"""

import pytest

from mem0_strands.client import Mem0ServiceClient, _extract_results, _is_platform_client


class FakeMemoryClient:
    """Stand-in for mem0.MemoryClient (platform: add/search take **kwargs)."""

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
    """Stand-in for mem0.Memory (OSS) with the real, strict signatures.

    ``search`` is keyword-only and rejects top-level entity params; ``add`` has a
    fixed signature with no ``**kwargs`` (so ``source`` or ``app_id`` is a
    ``TypeError``), exactly like the shipped SDK.
    """

    def __init__(self):
        self.add_calls = []
        self.search_calls = []

    def add(
        self,
        messages,
        *,
        user_id=None,
        agent_id=None,
        run_id=None,
        metadata=None,
        infer=True,
        timestamp=None,
        expiration_date=None,
        memory_type=None,
        prompt=None,
    ):
        self.add_calls.append(
            (
                messages,
                {"user_id": user_id, "agent_id": agent_id, "run_id": run_id, "metadata": metadata, "infer": infer},
            )
        )
        return {"results": []}

    def search(self, query, *, top_k=20, filters=None, threshold=0.1, **kwargs):
        rejected = kwargs.keys() & {"user_id", "agent_id", "run_id", "app_id"}
        if rejected:
            raise ValueError(f"Top-level entity parameters {set(rejected)} are not supported in search().")
        self.search_calls.append((query, {"top_k": top_k, "filters": filters}))
        return {"results": []}


class FakeAsyncMemoryClient:
    """Stand-in for mem0.AsyncMemoryClient: coroutine add/search."""

    async def add(self, messages, **kwargs):  # pragma: no cover - never called
        return {}

    async def search(self, query, **kwargs):  # pragma: no cover - never called
        return {}


def platform_client():
    """A Mem0ServiceClient wrapping a fake platform client."""
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    return Mem0ServiceClient(client=fake), fake


# ---------------------------------------------------------------------------
# backend detection
# ---------------------------------------------------------------------------


def test_detects_platform_by_class_name():
    assert _is_platform_client(FakeMemory()) is False
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    assert _is_platform_client(fake) is True


def test_injected_client_sets_platform_flag():
    fake = FakeMemoryClient()
    fake.__class__.__name__ = "MemoryClient"
    assert Mem0ServiceClient(client=fake).is_platform is True
    assert Mem0ServiceClient(client=FakeMemory()).is_platform is False


def test_async_client_is_rejected():
    """An async Mem0 client cannot be driven from a worker thread; reject it loudly."""
    with pytest.raises(ValueError, match="Async Mem0 clients are not supported"):
        Mem0ServiceClient(client=FakeAsyncMemoryClient())


# ---------------------------------------------------------------------------
# write routing
# ---------------------------------------------------------------------------


def test_store_memory_is_verbatim_and_tagged():
    """Platform store_memory writes infer=False, scope top-level, and a source tag."""
    client, fake = platform_client()

    client.store_memory("a fact", {"user_id": "alex"}, {"k": "v"})

    messages, kwargs = fake.add_calls[0]
    assert messages == "a fact"
    assert kwargs["infer"] is False
    assert kwargs["user_id"] == "alex"
    assert kwargs["metadata"] == {"k": "v"}
    assert kwargs["source"] == "STRANDS"


def test_store_messages_infers_and_tags():
    """Platform store_messages hands turns to Mem0 with infer=True and a source tag."""
    client, fake = platform_client()

    turns = [{"role": "user", "content": "hi"}]
    client.store_messages(turns, {"user_id": "alex"})

    messages, kwargs = fake.add_calls[0]
    assert messages == turns
    assert kwargs["infer"] is True
    assert kwargs["source"] == "STRANDS"


def test_oss_writes_omit_source():
    """OSS Memory.add has no source parameter, so the tag must be platform-only.

    (If the code passed source here, FakeMemory.add would raise TypeError.)
    """
    fake = FakeMemory()
    client = Mem0ServiceClient(client=fake)

    client.store_memory("a fact", {"user_id": "alex"}, None)
    client.store_messages([{"role": "user", "content": "hi"}], {"user_id": "alex"})

    assert len(fake.add_calls) == 2
    for _, kwargs in fake.add_calls:
        assert "source" not in kwargs


def test_oss_add_app_id_is_rejected():
    """app_id is platform-only; the OSS path fails loudly rather than TypeError-ing."""
    client = Mem0ServiceClient(client=FakeMemory())
    with pytest.raises(ValueError, match="platform-only"):
        client.store_memory("f", {"user_id": "alex", "app_id": "app1"}, None)


# ---------------------------------------------------------------------------
# search routing (filters + top_k on both backends)
# ---------------------------------------------------------------------------


def test_platform_search_uses_filters():
    """Platform search passes scope inside filters with top_k, never top-level."""
    client, fake = platform_client()

    client.search_memories("q", {"user_id": "alex"}, 5)

    _, kwargs = fake.search_calls[0]
    assert kwargs["filters"] == {"user_id": "alex"}
    assert kwargs["top_k"] == 5
    assert "user_id" not in kwargs


def test_oss_search_uses_filters():
    """OSS search also takes filters + top_k. The strict fake would raise on the
    old top-level/limit call shape, so this is the regression test for blocker 1."""
    fake = FakeMemory()
    client = Mem0ServiceClient(client=fake)

    client.search_memories("q", {"user_id": "alex"}, 5)

    _, recorded = fake.search_calls[0]
    assert recorded["filters"] == {"user_id": "alex"}
    assert recorded["top_k"] == 5


def test_oss_search_app_id_is_rejected():
    client = Mem0ServiceClient(client=FakeMemory())
    with pytest.raises(ValueError, match="platform-only"):
        client.search_memories("q", {"user_id": "alex", "app_id": "app1"}, 5)


# ---------------------------------------------------------------------------
# response normalization
# ---------------------------------------------------------------------------


def test_extract_results_shapes():
    assert _extract_results({"results": [{"id": 1}]}) == [{"id": 1}]
    assert _extract_results([{"id": 1}]) == [{"id": 1}]
    assert _extract_results({"nope": 1}) == []
    assert _extract_results(None) == []
