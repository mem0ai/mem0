"""Discriminating tests for the parallel semantic+BM25 search pipeline.

Sync path (Memory._search_vector_store): keyword_search is submitted to a
ThreadPoolExecutor first, embed runs on the main thread, semantic search is
submitted only after embed completes, and is_local backends stay sequential.

Async path (AsyncMemory._search_vector_store): embed and keyword_search run
via asyncio.gather, then semantic search runs sequentially after the gather.

Interleaving is verified with threading.Event handshakes -- no sleeps and no
timing thresholds, so the tests fail deterministically when parallelism is lost.

Failure contract (#6519 re-raise philosophy): semantic search and embed are on
the critical path, so their errors propagate; keyword_search is a best-effort
enhancement and degrades to None with a warning.
"""

import logging
import threading
from types import SimpleNamespace

import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.vector_stores.base import VectorStoreBase


def _mem(mem_id, score=0.9):
    """Build a vector-store search result entry."""
    return SimpleNamespace(
        id=mem_id,
        score=score,
        payload={
            "data": f"data-{mem_id}",
            "hash": f"hash-{mem_id}",
            "user_id": "alice",
            "created_at": "2023-05-06T09:19:20+00:00",
            "updated_at": "2023-05-06T09:19:20+00:00",
        },
    )


def _result_ids(results):
    return {item["id"] for item in results}


class _FakeKeywordStore:
    """Vector store that overrides keyword_search (parallel code path)."""

    is_local = False

    def __init__(
        self,
        semantic_results=None,
        keyword_results=None,
        semantic_error=None,
        keyword_error=None,
    ):
        self.semantic_results = list(semantic_results or [])
        self.keyword_results = list(keyword_results or [])
        self.semantic_error = semantic_error
        self.keyword_error = keyword_error
        self.keyword_calls = 0
        self.search_calls = 0
        self.keyword_thread = None
        self.search_thread = None
        self.seen_vectors = None
        # Per-test hooks invoked at the start of each call
        self.on_keyword_start = None
        self.on_search_start = None

    def search(self, query, vectors, top_k, filters):
        self.search_calls += 1
        self.search_thread = threading.current_thread()
        self.seen_vectors = vectors
        if self.on_search_start:
            self.on_search_start()
        if self.semantic_error:
            raise self.semantic_error
        return list(self.semantic_results)

    def keyword_search(self, query, top_k, filters):
        self.keyword_calls += 1
        self.keyword_thread = threading.current_thread()
        if self.on_keyword_start:
            self.on_keyword_start()
        if self.keyword_error:
            raise self.keyword_error
        return list(self.keyword_results)


class _FakeNoKeywordStore(_FakeKeywordStore):
    """Vector store that does NOT override keyword_search (sequential code path)."""

    keyword_search = VectorStoreBase.keyword_search


class _FakeEmbedder:
    """Embedding model whose embed() can participate in Event handshakes."""

    def __init__(self, vector=None, error=None):
        self.vector = vector or [0.1, 0.2, 0.3]
        self.error = error
        self.calls = 0
        self.on_embed_start = None

    def embed(self, text, usage):
        self.calls += 1
        if self.on_embed_start:
            self.on_embed_start()
        if self.error:
            raise self.error
        return self.vector


def _make_memory(memory_cls, store, embedder):
    """Build a Memory/AsyncMemory without running __init__.

    _search_vector_store only touches embedding_model and vector_store (entity
    boosts are skipped for entity-free queries like "pizza"), so a bare instance
    avoids the full factory mocking used by tests/memory/test_main.py.
    """
    memory = memory_cls.__new__(memory_cls)
    memory.embedding_model = embedder
    memory.vector_store = store
    return memory


class TestSyncParallelSearch:
    def _run(self, store, embedder):
        memory = _make_memory(Memory, store, embedder)
        return memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10)

    def test_keyword_search_overlaps_embed(self):
        """keyword_search and embed must run concurrently (bidirectional handshake)."""
        keyword_started = threading.Event()
        embed_started = threading.Event()
        saw = {}

        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])

        def on_keyword_start():
            keyword_started.set()
            saw["keyword_saw_embed"] = embed_started.wait(timeout=5)

        store.on_keyword_start = on_keyword_start

        embedder = _FakeEmbedder()

        def on_embed_start():
            embed_started.set()
            saw["embed_saw_keyword"] = keyword_started.wait(timeout=5)

        embedder.on_embed_start = on_embed_start

        results = self._run(store, embedder)

        assert saw["embed_saw_keyword"] is True, "embed finished without keyword_search ever starting (no overlap)"
        assert saw["keyword_saw_embed"] is True, "keyword_search finished without embed ever starting (no overlap)"
        assert _result_ids(results) == {"mem-1"}

    def test_semantic_search_overlaps_keyword_and_uses_embed_output(self):
        """Semantic search starts on a pool thread while keyword_search is still
        blocked, and receives the embedder's output (submitted after embed)."""
        semantic_started = threading.Event()
        keyword_report = {}

        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])

        def on_keyword_start():
            keyword_report["saw_semantic_start"] = semantic_started.wait(timeout=5)

        store.on_keyword_start = on_keyword_start

        def on_search_start():
            semantic_started.set()

        store.on_search_start = on_search_start

        embedder = _FakeEmbedder(vector=[0.4, 0.5])
        results = self._run(store, embedder)

        assert keyword_report["saw_semantic_start"] is True, (
            "semantic search never started while keyword_search was in flight (sync path lost parallelism)"
        )
        assert store.search_thread is not threading.main_thread()
        assert store.seen_vectors == [0.4, 0.5]
        assert _result_ids(results) == {"mem-1"}

    def test_store_without_keyword_override_takes_sequential_path(self):
        """Stores that don't override keyword_search never have it called."""
        store = _FakeNoKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_results=[_mem("mem-2")],
        )
        results = self._run(store, _FakeEmbedder())

        assert store.keyword_calls == 0
        assert store.search_thread is threading.main_thread()
        assert _result_ids(results) == {"mem-1"}

    def test_local_backend_takes_sequential_path(self):
        """is_local stores must keep every call on the main thread (SQLite
        check_same_thread guard)."""
        store = _FakeKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_results=[_mem("mem-2")],
        )
        store.is_local = True
        results = self._run(store, _FakeEmbedder())

        assert store.keyword_calls == 1
        assert store.keyword_thread is threading.main_thread(), (
            "keyword_search ran off the main thread for a local backend"
        )
        assert store.search_thread is threading.main_thread()
        assert _result_ids(results) == {"mem-1"}

    def test_keyword_failure_degrades_to_semantic_only(self, caplog):
        """keyword_search failure must degrade to None and keep semantic results."""
        store = _FakeKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_error=RuntimeError("kw boom"),
        )
        with caplog.at_level(logging.WARNING, logger="mem0.memory.main"):
            results = self._run(store, _FakeEmbedder())

        assert _result_ids(results) == {"mem-1"}
        assert store.keyword_calls == 1
        assert any("Keyword search failed" in record.message for record in caplog.records)

    def test_semantic_failure_propagates(self):
        """semantic search failure must propagate (re-raise, #6519 philosophy),
        not silently degrade to [] which would mask a retrieval outage."""
        store = _FakeKeywordStore(
            semantic_error=RuntimeError("sem boom"),
            keyword_results=[_mem("mem-2")],
        )
        with pytest.raises(RuntimeError, match="sem boom"):
            self._run(store, _FakeEmbedder())

        assert store.search_calls == 1

    def test_both_failures_propagate_semantic_error(self):
        """When both searches fail, the semantic error must propagate (keyword
        failure stays degraded to None as best-effort enhancement)."""
        store = _FakeKeywordStore(
            semantic_error=RuntimeError("sem boom"),
            keyword_error=RuntimeError("kw boom"),
        )
        with pytest.raises(RuntimeError, match="sem boom"):
            self._run(store, _FakeEmbedder())

        assert store.search_calls == 1
        assert store.keyword_calls == 1

    def test_embed_failure_propagates(self):
        """embed failure must propagate like semantic failure (consistent
        failure contract on the critical path)."""
        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])
        embedder = _FakeEmbedder(error=RuntimeError("embed boom"))

        with pytest.raises(RuntimeError, match="embed boom"):
            self._run(store, embedder)

        # semantic search never ran (it needs the embedding)
        assert store.search_calls == 0


class TestAsyncParallelSearch:
    async def _run(self, store, embedder):
        memory = _make_memory(AsyncMemory, store, embedder)
        return await memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10)

    @pytest.mark.asyncio
    async def test_embed_overlaps_keyword(self):
        """embed and keyword_search must run concurrently (bidirectional handshake)."""
        keyword_started = threading.Event()
        embed_started = threading.Event()
        saw = {}

        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])

        def on_keyword_start():
            keyword_started.set()
            saw["keyword_saw_embed"] = embed_started.wait(timeout=5)

        store.on_keyword_start = on_keyword_start

        embedder = _FakeEmbedder()

        def on_embed_start():
            embed_started.set()
            saw["embed_saw_keyword"] = keyword_started.wait(timeout=5)

        embedder.on_embed_start = on_embed_start

        results = await self._run(store, embedder)

        assert saw["embed_saw_keyword"] is True, "embed finished without keyword_search ever starting (no overlap)"
        assert saw["keyword_saw_embed"] is True, "keyword_search finished without embed ever starting (no overlap)"
        assert _result_ids(results) == {"mem-1"}

    @pytest.mark.asyncio
    async def test_semantic_starts_only_after_keyword_completes(self):
        """Async path gathers embed+keyword first; a slow keyword_search must delay
        the start of semantic search. This locks the current sequential-semantic
        boundary of the async implementation."""
        semantic_started = threading.Event()
        keyword_report = {}

        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])

        def on_keyword_start():
            keyword_report["saw_semantic_start"] = semantic_started.wait(timeout=0.3)
            keyword_report["search_calls_at_keyword_exit"] = store.search_calls

        store.on_keyword_start = on_keyword_start

        def on_search_start():
            semantic_started.set()

        store.on_search_start = on_search_start

        results = await self._run(store, _FakeEmbedder())

        assert keyword_report["saw_semantic_start"] is False, (
            "semantic search started while keyword_search was still running"
        )
        assert keyword_report["search_calls_at_keyword_exit"] == 0
        assert store.search_calls == 1
        assert _result_ids(results) == {"mem-1"}

    @pytest.mark.asyncio
    async def test_store_without_keyword_override_takes_sequential_path(self):
        """Stores that don't override keyword_search never have it called."""
        store = _FakeNoKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_results=[_mem("mem-2")],
        )
        results = await self._run(store, _FakeEmbedder())

        assert store.keyword_calls == 0
        assert store.search_calls == 1
        assert _result_ids(results) == {"mem-1"}

    @pytest.mark.asyncio
    async def test_local_backend_takes_sequential_path(self):
        """is_local stores must skip gather-based concurrency (SQLite
        check_same_thread guard) and still return correct results."""
        store = _FakeKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_results=[_mem("mem-2")],
        )
        store.is_local = True
        results = await self._run(store, _FakeEmbedder())

        assert store.keyword_calls == 1
        assert store.search_calls == 1
        assert _result_ids(results) == {"mem-1"}

    @pytest.mark.asyncio
    async def test_keyword_failure_degrades_to_semantic_only(self, caplog):
        """keyword_search failure must degrade to None and keep semantic results."""
        store = _FakeKeywordStore(
            semantic_results=[_mem("mem-1")],
            keyword_error=RuntimeError("kw boom"),
        )
        with caplog.at_level(logging.WARNING, logger="mem0.memory.main"):
            results = await self._run(store, _FakeEmbedder())

        assert _result_ids(results) == {"mem-1"}
        assert store.keyword_calls == 1
        assert any("Keyword search failed" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_semantic_failure_propagates(self):
        """semantic search failure must propagate (re-raise, #6519 philosophy),
        not silently degrade to [] which would mask a retrieval outage."""
        store = _FakeKeywordStore(
            semantic_error=RuntimeError("sem boom"),
            keyword_results=[_mem("mem-2")],
        )
        with pytest.raises(RuntimeError, match="sem boom"):
            await self._run(store, _FakeEmbedder())

        assert store.search_calls == 1

    @pytest.mark.asyncio
    async def test_both_failures_propagate_semantic_error(self):
        """When both searches fail, the semantic error must propagate (keyword
        failure stays degraded to None as best-effort enhancement)."""
        store = _FakeKeywordStore(
            semantic_error=RuntimeError("sem boom"),
            keyword_error=RuntimeError("kw boom"),
        )
        with pytest.raises(RuntimeError, match="sem boom"):
            await self._run(store, _FakeEmbedder())

        assert store.search_calls == 1
        assert store.keyword_calls == 1

    @pytest.mark.asyncio
    async def test_embed_failure_propagates(self):
        """embed failure must propagate like semantic failure (consistent
        failure contract on the critical path)."""
        store = _FakeKeywordStore(semantic_results=[_mem("mem-1")])
        embedder = _FakeEmbedder(error=RuntimeError("embed boom"))

        with pytest.raises(RuntimeError, match="embed boom"):
            await self._run(store, embedder)

        # semantic search never ran (it needs the embedding)
        assert store.search_calls == 0
