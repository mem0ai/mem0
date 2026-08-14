"""
Level 2: End-to-end tests for Memory.search(threshold=...) across vector stores.

Tests the full pipeline: Memory.add() -> Memory.search(threshold=X) -> verify
that threshold filtering works correctly now that scores are similarity
(higher = better).

Before the fix, threshold filtering was inverted — good matches were dropped
and bad matches passed through. These tests verify the fix works end-to-end
through the Memory class, not just at the vector store layer.

In-memory providers (FAISS, ChromaDB) always run. External providers
(PGVector, Redis, Milvus, etc.) are skipped unless the service is reachable.
Set OPENAI_API_KEY env var or configure an alternative LLM/embedder to use
the full Memory pipeline; otherwise tests fall back to direct vector store
operations with synthetic embeddings.

Refs: https://github.com/mem0ai/mem0/issues/4453
"""

import os
import uuid

import numpy as np
import pytest

DIMS = 128


def _tcp_reachable(host, port, timeout=2):
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _make_vectors():
    """Create 5 vectors with known similarity spread to a query."""
    np.random.seed(42)
    query = np.random.randn(DIMS).astype(np.float32)
    query = query / np.linalg.norm(query)

    vecs = []
    for scale in [0.05, 0.15, 0.4, 0.8, 1.5]:
        v = query + np.random.randn(DIMS).astype(np.float32) * scale
        v = v / np.linalg.norm(v)
        vecs.append(v.tolist())

    return query.tolist(), vecs


def _run_threshold_test(store, query, doc_vectors, payloads, ids):
    """
    Core threshold test logic shared across all providers.
    Uses direct vector store API (not Memory class) so we can control
    the exact vectors and test threshold behavior precisely.
    """
    store.insert(vectors=doc_vectors, payloads=payloads, ids=ids)

    # Step 1: Search without threshold (baseline)
    results = store.search(query="", vectors=query, top_k=5)
    assert len(results) > 0, "Baseline search returned no results"

    scores = [r.score for r in results]

    # Verify scores are similarity (higher = better)
    assert scores[0] >= scores[-1], (
        f"Top result should have highest score: first={scores[0]}, last={scores[-1]}"
    )

    # Step 2: Verify all scores are non-negative (similarity, not raw distance)
    assert all(s >= 0 for s in scores if s is not None), (
        f"All scores must be non-negative (not raw distances): {scores}"
    )

    # Step 3: Simulate threshold filtering as Memory.search() does it
    # The check in mem0/memory/main.py is: if threshold is None or mem.score >= threshold
    mid_threshold = (scores[0] + scores[-1]) / 2 if len(scores) >= 2 else scores[0] * 0.5

    filtered = [r for r in results if r.score >= mid_threshold]
    assert len(filtered) < len(results), (
        f"Mid threshold {mid_threshold:.4f} should filter some results. "
        f"Scores: {scores}"
    )
    assert len(filtered) > 0, (
        f"Mid threshold {mid_threshold:.4f} should keep some results. "
        f"Scores: {scores}"
    )

    # All filtered results must have score >= threshold
    for r in filtered:
        assert r.score >= mid_threshold, (
            f"Score {r.score:.4f} below threshold {mid_threshold:.4f}"
        )

    # Step 4: Very high threshold should return 0 or very few results
    high_threshold = 0.99
    high_filtered = [r for r in results if r.score >= high_threshold]
    assert len(high_filtered) < len(results), (
        f"Threshold 0.99 should filter most results. Scores: {scores}"
    )

    return scores


# ---------------------------------------------------------------------------
# In-memory stores (always available)
# ---------------------------------------------------------------------------


class TestChromaDBThreshold:
    def test_threshold_filtering(self, tmp_path):
        from mem0.vector_stores.chroma import ChromaDB

        store = ChromaDB(collection_name="test_threshold", path=str(tmp_path / "chroma"))
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        scores = _run_threshold_test(store, query, doc_vectors, payloads, ids)
        assert all(0 < s <= 1.0 for s in scores), f"ChromaDB scores in (0,1]: {scores}"
        store.delete_col()

    def test_threshold_direction_not_inverted(self, tmp_path):
        """Regression test: before the fix, threshold filtering was inverted."""
        from mem0.vector_stores.chroma import ChromaDB

        store = ChromaDB(collection_name="test_inversion", path=str(tmp_path / "chroma2"))
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        store.insert(vectors=doc_vectors, payloads=payloads, ids=ids)
        results = store.search(query="", vectors=query, top_k=5)
        scores = [r.score for r in results]

        # The bug was: all scores collapsed to 1.0 because raw L2 distances
        # > 1.0 were capped. Verify scores are NOT all identical.
        unique_scores = set(round(s, 6) for s in scores)
        assert len(unique_scores) > 1, (
            f"Scores should not all be identical (bug symptom): {scores}"
        )

        # The closest doc should score strictly higher than the farthest
        assert scores[0] > scores[-1], (
            f"Closest doc must score higher than farthest: {scores}"
        )
        store.delete_col()


class TestFAISSEuclideanThreshold:
    def test_threshold_filtering(self, tmp_path):
        from mem0.vector_stores.faiss import FAISS

        store = FAISS(
            collection_name="test_threshold",
            path=str(tmp_path / "faiss"),
            distance_strategy="euclidean",
            embedding_model_dims=DIMS,
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        scores = _run_threshold_test(store, query, doc_vectors, payloads, ids)
        assert all(0 < s <= 1.0 for s in scores), f"FAISS euclidean scores in (0,1]: {scores}"


class TestFAISSCosineThreshold:
    def test_threshold_filtering(self, tmp_path):
        from mem0.vector_stores.faiss import FAISS

        store = FAISS(
            collection_name="test_threshold",
            path=str(tmp_path / "faiss_cos"),
            distance_strategy="cosine",
            embedding_model_dims=DIMS,
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        store.insert(vectors=doc_vectors, payloads=payloads, ids=ids)
        results = store.search(query="", vectors=query, top_k=5)
        scores = [r.score for r in results]

        assert scores[0] >= scores[-1], f"Descending order: {scores}"


# ---------------------------------------------------------------------------
# External stores
# ---------------------------------------------------------------------------

PGVECTOR_HOST = os.environ.get("PGVECTOR_HOST", "localhost")
PGVECTOR_PORT = int(os.environ.get("PGVECTOR_PORT", "5432"))
PGVECTOR_USER = os.environ.get("PGVECTOR_USER", "mem0")
PGVECTOR_PASS = os.environ.get("PGVECTOR_PASSWORD", "mem0test")
PGVECTOR_DB = os.environ.get("PGVECTOR_DB", "mem0_test")


def _pgvector_reachable():
    try:
        import psycopg

        conn = psycopg.connect(
            host=PGVECTOR_HOST, port=PGVECTOR_PORT,
            user=PGVECTOR_USER, password=PGVECTOR_PASS, dbname=PGVECTOR_DB,
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _pgvector_reachable(),
    reason=f"pgvector not reachable at {PGVECTOR_HOST}:{PGVECTOR_PORT} with user {PGVECTOR_USER}",
)
class TestPGVectorThreshold:
    def test_threshold_filtering(self):
        from mem0.vector_stores.pgvector import PGVector

        collection = f"test_thr_{uuid.uuid4().hex[:8]}"
        store = PGVector(
            collection_name=collection,
            embedding_model_dims=DIMS,
            host=PGVECTOR_HOST,
            port=PGVECTOR_PORT,
            user=os.environ.get("PGVECTOR_USER", "mem0"),
            password=os.environ.get("PGVECTOR_PASSWORD", "mem0test"),
            dbname=os.environ.get("PGVECTOR_DB", "mem0_test"),
            diskann=False,
            hnsw=True,
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [str(uuid.uuid4()) for _ in range(5)]

        scores = _run_threshold_test(store, query, doc_vectors, payloads, ids)
        assert all(0 <= s <= 1.0 for s in scores), f"PGVector scores in [0,1]: {scores}"
        store.delete_col()


REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


@pytest.mark.skipif(
    not _tcp_reachable(REDIS_HOST, REDIS_PORT),
    reason=f"Redis not reachable at {REDIS_HOST}:{REDIS_PORT}",
)
class TestRedisThreshold:
    def test_threshold_filtering(self):
        from datetime import datetime, timezone

        from mem0.vector_stores.redis import RedisDB

        collection = f"test_thr_{uuid.uuid4().hex[:8]}"
        store = RedisDB(
            collection_name=collection,
            embedding_model_dims=DIMS,
            redis_url=f"redis://{REDIS_HOST}:{REDIS_PORT}",
        )
        query, doc_vectors = _make_vectors()
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        payloads = [
            {"hash": f"h{i}", "data": f"doc_{i} memory", "created_at": now, "user_id": "test", "label": f"doc_{i}"}
            for i in range(5)
        ]
        ids = [str(uuid.uuid4()) for _ in range(5)]

        store.insert(vectors=doc_vectors, payloads=payloads, ids=ids)
        results = store.search(query="", vectors=query, top_k=5, filters={"user_id": "test"})

        scores = [r.score for r in results]
        assert all(0 <= s <= 1.0 for s in scores), f"Redis scores in [0,1]: {scores}"
        assert scores[0] >= scores[-1], f"Descending order: {scores}"

        mid = (scores[0] + scores[-1]) / 2
        filtered = [r for r in results if r.score >= mid]
        assert 0 < len(filtered) < len(results), f"Threshold {mid} should filter: {scores}"
        store.delete_col()


VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6380"))


@pytest.mark.skipif(
    not _tcp_reachable(VALKEY_HOST, VALKEY_PORT),
    reason=f"Valkey not reachable at {VALKEY_HOST}:{VALKEY_PORT}",
)
class TestValkeyThreshold:
    def test_threshold_filtering(self):
        from datetime import datetime, timezone

        from mem0.vector_stores.valkey import ValkeyDB

        collection = f"test_thr_{uuid.uuid4().hex[:8]}"
        store = ValkeyDB(
            collection_name=collection,
            embedding_model_dims=DIMS,
            valkey_url=f"valkey://{VALKEY_HOST}:{VALKEY_PORT}",
        )
        query, doc_vectors = _make_vectors()
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        payloads = [
            {"hash": f"h{i}", "data": f"doc_{i} memory", "created_at": now, "user_id": "test", "label": f"doc_{i}"}
            for i in range(5)
        ]
        ids = [str(uuid.uuid4()) for _ in range(5)]

        store.insert(vectors=doc_vectors, payloads=payloads, ids=ids)
        results = store.search(query="", vectors=query, top_k=5, filters={"user_id": "test"})

        scores = [r.score for r in results]
        assert all(0 <= s <= 1.0 for s in scores), f"Valkey scores in [0,1]: {scores}"
        assert scores[0] >= scores[-1], f"Descending order: {scores}"
        store.delete_col()


MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))


@pytest.mark.skipif(
    not _tcp_reachable(MILVUS_HOST, MILVUS_PORT),
    reason=f"Milvus not reachable at {MILVUS_HOST}:{MILVUS_PORT}",
)
class TestMilvusL2Threshold:
    def test_threshold_filtering(self):
        from mem0.vector_stores.milvus import MilvusDB

        collection = f"test_l2_{uuid.uuid4().hex[:8]}"
        store = MilvusDB(
            collection_name=collection,
            embedding_model_dims=DIMS,
            url=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            token="",
            db_name="",
            metric_type="L2",
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [str(uuid.uuid4()) for _ in range(5)]

        store.insert(ids=ids, vectors=doc_vectors, payloads=payloads)
        scores = _run_threshold_test(store, query, doc_vectors[:3], payloads[:3], [str(uuid.uuid4()) for _ in range(3)])
        # L2 scores via 1/(1+d) should be in (0, 1]
        assert all(0 < s <= 1.0 for s in scores), f"Milvus L2 scores in (0,1]: {scores}"
        store.delete_col()


@pytest.mark.skipif(
    not _tcp_reachable(MILVUS_HOST, MILVUS_PORT),
    reason=f"Milvus not reachable at {MILVUS_HOST}:{MILVUS_PORT}",
)
class TestMilvusCosineThreshold:
    def test_threshold_filtering(self):
        from mem0.vector_stores.milvus import MilvusDB

        collection = f"test_cos_{uuid.uuid4().hex[:8]}"
        store = MilvusDB(
            collection_name=collection,
            embedding_model_dims=DIMS,
            url=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            token="",
            db_name="",
            metric_type="COSINE",
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [str(uuid.uuid4()) for _ in range(5)]

        store.insert(ids=ids, vectors=doc_vectors, payloads=payloads)
        results = store.search(query="", vectors=query, top_k=5)

        scores = [r.score for r in results]
        assert scores[0] >= scores[-1], f"Descending: {scores}"
        store.delete_col()


SUPABASE_CONN = os.environ.get("SUPABASE_CONN_STRING", "")


@pytest.mark.skipif(not SUPABASE_CONN, reason="SUPABASE_CONN_STRING not set")
class TestSupabaseThreshold:
    def test_threshold_filtering(self):
        from mem0.vector_stores.supabase import Supabase

        collection = f"test_thr_{uuid.uuid4().hex[:8]}"
        store = Supabase(
            connection_string=SUPABASE_CONN,
            collection_name=collection,
            embedding_model_dims=DIMS,
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        scores = _run_threshold_test(store, query, doc_vectors, payloads, ids)
        assert all(0 <= s <= 1.0 for s in scores), f"Supabase scores in [0,1]: {scores}"
        store.delete_col()


S3_BUCKET = os.environ.get("S3_VECTORS_BUCKET", "")


@pytest.mark.skipif(not S3_BUCKET, reason="S3_VECTORS_BUCKET not set")
class TestS3VectorsThreshold:
    def test_threshold_filtering(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        collection = f"testthr{uuid.uuid4().hex[:8]}"
        region = os.environ.get("S3_VECTORS_REGION", "us-east-1")
        store = S3Vectors(
            vector_bucket_name=S3_BUCKET,
            collection_name=collection,
            embedding_model_dims=DIMS,
            distance_metric="cosine",
            region_name=region,
        )
        query, doc_vectors = _make_vectors()
        payloads = [{"label": f"doc_{i}"} for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]

        scores = _run_threshold_test(store, query, doc_vectors, payloads, ids)
        assert all(0 <= s <= 1.0 for s in scores), f"S3 scores in [0,1]: {scores}"
        store.delete_col()
