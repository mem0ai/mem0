"""Tests for ScopedMemoryClient.

These verify the wrapper boundary: every operation injects user_id in the
shape mem0 currently requires, an empty user_id is rejected at construction
time, and two scoped clients with different user_ids never share state.

The tests use a minimal stub for the underlying mem0 client so they can run
without OpenAI / Qdrant / Ollama.
"""

from __future__ import annotations

import os

# Quiet env-var-required imports inside the wrapper module's transitive deps.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils.scoped_client import ScopedMemoryClient


class StubVectorStore:
    """Records the last search call so tests can assert on the filter shape."""

    def __init__(self):
        self.last_call: dict | None = None

    def search(self, *, query, vectors, top_k, filters):
        self.last_call = {
            "query": query,
            "vectors": vectors,
            "top_k": top_k,
            "filters": filters,
        }
        return []


class StubEmbeddingModel:
    def embed(self, query: str, kind: str):
        return [0.0, 0.0, 0.0]


class StubMemoryClient:
    """Minimal mem0-shaped client. Records every call for later inspection."""

    def __init__(self):
        self.embedding_model = StubEmbeddingModel()
        self.vector_store = StubVectorStore()
        self.add_calls: list[dict] = []
        self.get_all_calls: list[dict] = []
        self.delete_calls: list[str] = []

    def add(self, text, *, user_id, metadata, infer):
        self.add_calls.append(
            {"text": text, "user_id": user_id, "metadata": metadata, "infer": infer}
        )
        return {"results": [{"id": "00000000-0000-0000-0000-000000000001",
                             "memory": text, "event": "ADD", "hash": "h"}]}

    def get_all(self, *, filters, top_k):
        if not isinstance(filters, dict) or "user_id" not in filters:
            raise ValueError(
                "Top-level entity parameters not supported in get_all(). "
                "Use filters={'user_id': '...'} instead."
            )
        self.get_all_calls.append({"filters": filters, "top_k": top_k})
        return {"results": []}

    def delete(self, memory_id: str):
        self.delete_calls.append(memory_id)


# ---------------------------------------------------------------------------
# Constructor invariants
# ---------------------------------------------------------------------------

def test_rejects_empty_user_id():
    with pytest.raises(ValueError, match="non-empty user_id"):
        ScopedMemoryClient(StubMemoryClient(), "")


def test_rejects_none_user_id():
    with pytest.raises(ValueError, match="non-empty user_id"):
        ScopedMemoryClient(StubMemoryClient(), None)  # type: ignore[arg-type]


def test_rejects_none_client():
    with pytest.raises(ValueError, match="initialized memory client"):
        ScopedMemoryClient(None, "u1")  # type: ignore[arg-type]


def test_user_id_property_exposes_uid():
    s = ScopedMemoryClient(StubMemoryClient(), "u1")
    assert s.user_id == "u1"
    assert s.filters == {"user_id": "u1"}


# ---------------------------------------------------------------------------
# Method-level scoping invariants
# ---------------------------------------------------------------------------

def test_add_injects_user_id_top_level():
    inner = StubMemoryClient()
    s = ScopedMemoryClient(inner, "u1")
    s.add("hello", metadata={"k": "v"}, infer=False)
    assert inner.add_calls == [
        {"text": "hello", "user_id": "u1", "metadata": {"k": "v"}, "infer": False}
    ]


def test_add_default_metadata_is_empty_dict():
    inner = StubMemoryClient()
    ScopedMemoryClient(inner, "u1").add("hello")
    assert inner.add_calls[0]["metadata"] == {}
    assert inner.add_calls[0]["infer"] is True


def test_get_all_injects_filters_dict():
    inner = StubMemoryClient()
    ScopedMemoryClient(inner, "u1").get_all(top_k=42)
    assert inner.get_all_calls == [{"filters": {"user_id": "u1"}, "top_k": 42}]


def test_get_all_default_top_k_is_1000():
    inner = StubMemoryClient()
    ScopedMemoryClient(inner, "u1").get_all()
    assert inner.get_all_calls[0]["top_k"] == 1000


def test_search_passes_filters_to_vector_store():
    inner = StubMemoryClient()
    ScopedMemoryClient(inner, "u1").search("hello", top_k=5)
    assert inner.vector_store.last_call is not None
    assert inner.vector_store.last_call["filters"] == {"user_id": "u1"}
    assert inner.vector_store.last_call["top_k"] == 5
    assert inner.vector_store.last_call["query"] == "hello"


def test_delete_passes_memory_id_unchanged():
    inner = StubMemoryClient()
    ScopedMemoryClient(inner, "u1").delete("mem-123")
    assert inner.delete_calls == ["mem-123"]


# ---------------------------------------------------------------------------
# Isolation invariants — two scoped clients never bleed
# ---------------------------------------------------------------------------

def test_two_scoped_clients_have_independent_filters():
    inner = StubMemoryClient()
    s_a = ScopedMemoryClient(inner, "TpGroup")
    s_b = ScopedMemoryClient(inner, "OtherProject")
    s_a.get_all()
    s_b.get_all()
    assert inner.get_all_calls[0]["filters"] == {"user_id": "TpGroup"}
    assert inner.get_all_calls[1]["filters"] == {"user_id": "OtherProject"}


def test_user_id_is_immutable_on_instance():
    s = ScopedMemoryClient(StubMemoryClient(), "u1")
    # Reading is fine
    assert s.user_id == "u1"
    # Setting through the property is rejected (no setter defined)
    with pytest.raises(AttributeError):
        s.user_id = "u2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Regression — surfacing of the original bug
# ---------------------------------------------------------------------------

def test_get_all_does_not_pass_top_level_user_id():
    """Regression for the list_memories bug: mem0 rejects top-level user_id."""

    class StrictClient(StubMemoryClient):
        def get_all(self, **kwargs):  # type: ignore[override]
            if "user_id" in kwargs and "filters" not in kwargs:
                raise TypeError(
                    "Top-level entity parameters frozenset({'user_id'}) "
                    "are not supported in get_all(). Use filters=... instead."
                )
            return super().get_all(**kwargs)

    s = ScopedMemoryClient(StrictClient(), "u1")
    # Must not raise.
    s.get_all()
