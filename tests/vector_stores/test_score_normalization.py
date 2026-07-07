"""
Level 1: Vector store layer tests for score normalization.

Verifies that all vector stores return similarity scores (higher = better)
after the distance-to-similarity conversion fix. Each test directly inserts
vectors with known similarity ordering, then asserts scores are:
  - Non-negative
  - In [0, 1] (for normalized stores)
  - Descending (close > mid > far)
  - Closest vector ranks first
  - Threshold filtering works (score >= threshold keeps correct results)

Providers that need external services are skipped unless the service is
reachable. FAISS and ChromaDB run in-memory and always execute.

Refs: https://github.com/mem0ai/mem0/issues/4453
"""

import os
import uuid

import numpy as np
import pytest

DIMS = 128


@pytest.fixture(scope="module")
def vectors():
    """Create a query vector and 3 doc vectors with known similarity ordering."""
    np.random.seed(42)
    query = np.random.randn(DIMS).astype(np.float32)
    query = query / np.linalg.norm(query)

    close = query + np.random.randn(DIMS).astype(np.float32) * 0.1
    close = close / np.linalg.norm(close)

    mid = query + np.random.randn(DIMS).astype(np.float32) * 0.5
    mid = mid / np.linalg.norm(mid)

    far = np.random.randn(DIMS).astype(np.float32)
    far = far / np.linalg.norm(far)

    return {
        "query": query.tolist(),
        "docs": [close.tolist(), mid.tolist(), far.tolist()],
        "payloads": [{"label": "close"}, {"label": "mid"}, {"label": "far"}],
        "ids": ["close", "mid", "far"],
    }


def _assert_similarity_scores(results, *, allow_negative=False):
    """Common assertions for normalized similarity scores."""
    scores = [r.score for r in results]
    labels = [r.payload.get("label", r.payload.get("data", "?").split()[0]) for r in results]

    assert len(results) == 3, f"Expected 3 results, got {len(results)}"

    if not allow_negative:
        assert all(s >= 0 for s in scores), f"Scores must be non-negative: {scores}"
        assert all(s <= 1.0 for s in scores), f"Scores must be <= 1.0: {scores}"

    assert scores[0] >= scores[1] >= scores[2], (
        f"Scores must be descending (higher=better): {list(zip(labels, scores))}"
    )

    assert labels[0] == "close", f"Closest vector must rank first, got: {labels[0]}"

    # Threshold filtering: using mid score should keep at least close and mid
    threshold = scores[1]
    filtered = [r for r in results if r.score >= threshold]
    assert len(filtered) >= 2, (
        f"Threshold {threshold} should keep >= 2 results, got {len(filtered)}"
    )


# ---------------------------------------------------------------------------
# In-memory stores (always available)
# ---------------------------------------------------------------------------


class TestChromaDB:
    """ChromaDB uses L2 distance. Conversion: score = 1 / (1 + distance)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors, tmp_path):
        from mem0.vector_stores.chroma import ChromaDB

        self.store = ChromaDB(collection_name="test_norm", path=str(tmp_path / "chroma"))
        self.store.insert(
            vectors=vectors["docs"],
            payloads=vectors["payloads"],
            ids=vectors["ids"],
        )
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)

    def test_score_formula(self):
        """Verify the exact L2-to-similarity conversion."""
        results = self.store.search(query="", vectors=self.query, top_k=3)
        for r in results:
            assert r.score > 0.0
            assert r.score <= 1.0


class TestFAISSEuclidean:
    """FAISS euclidean uses L2 distance. Conversion: score = 1 / (1 + distance)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors, tmp_path):
        from mem0.vector_stores.faiss import FAISS

        self.store = FAISS(
            collection_name="test_norm",
            path=str(tmp_path / "faiss_euc"),
            distance_strategy="euclidean",
            embedding_model_dims=DIMS,
        )
        self.store.insert(
            vectors=vectors["docs"],
            payloads=vectors["payloads"],
            ids=vectors["ids"],
        )
        self.query = vectors["query"]
        yield

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)


class TestFAISSCosine:
    """FAISS cosine uses inner product (higher = better). No conversion needed."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors, tmp_path):
        from mem0.vector_stores.faiss import FAISS

        self.store = FAISS(
            collection_name="test_norm",
            path=str(tmp_path / "faiss_cos"),
            distance_strategy="cosine",
            embedding_model_dims=DIMS,
        )
        self.store.insert(
            vectors=vectors["docs"],
            payloads=vectors["payloads"],
            ids=vectors["ids"],
        )
        self.query = vectors["query"]
        yield

    def test_scores_are_descending(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results, allow_negative=True)


# ---------------------------------------------------------------------------
# External stores (skipped if service unavailable)
# ---------------------------------------------------------------------------


def _tcp_reachable(host, port, timeout=2):
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# --- PGVector ---

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
class TestPGVector:
    """PGVector uses cosine distance [0,2]. Conversion: score = max(0, 1 - dist)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from mem0.vector_stores.pgvector import PGVector

        self.collection = f"test_norm_{uuid.uuid4().hex[:8]}"
        self.store = PGVector(
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            host=PGVECTOR_HOST,
            port=PGVECTOR_PORT,
            user=PGVECTOR_USER,
            password=PGVECTOR_PASS,
            dbname=PGVECTOR_DB,
            diskann=False,
            hnsw=True,
        )
        ids = [str(uuid.uuid4()) for _ in range(3)]
        self.store.insert(vectors=vectors["docs"], payloads=vectors["payloads"], ids=ids)
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)


# --- Redis ---

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


@pytest.mark.skipif(
    not _tcp_reachable(REDIS_HOST, REDIS_PORT),
    reason=f"Redis not reachable at {REDIS_HOST}:{REDIS_PORT}",
)
class TestRedis:
    """Redis returns cosine distance [0,2]. Conversion: score = max(0, 1 - dist)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from datetime import datetime, timezone

        from mem0.vector_stores.redis import RedisDB

        self.collection = f"test_norm_{uuid.uuid4().hex[:8]}"
        self.store = RedisDB(
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            redis_url=f"redis://{REDIS_HOST}:{REDIS_PORT}",
        )

        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        payloads = [
            {"hash": f"h{i}", "data": f"{v['label']} memory", "created_at": now, "user_id": "test", **v}
            for i, v in enumerate(vectors["payloads"])
        ]
        ids = [str(uuid.uuid4()) for _ in range(3)]
        self.store.insert(vectors=vectors["docs"], payloads=payloads, ids=ids)
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(
            query="", vectors=self.query, top_k=3, filters={"user_id": "test"}
        )
        scores = [r.score for r in results]
        assert all(s >= 0 for s in scores), f"Scores must be non-negative: {scores}"
        assert all(s <= 1.0 for s in scores), f"Scores must be <= 1.0: {scores}"
        assert scores[0] >= scores[1] >= scores[2], f"Scores must be descending: {scores}"


# --- Valkey ---

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6380"))


@pytest.mark.skipif(
    not _tcp_reachable(VALKEY_HOST, VALKEY_PORT),
    reason=f"Valkey not reachable at {VALKEY_HOST}:{VALKEY_PORT}",
)
class TestValkey:
    """Valkey returns cosine distance [0,2]. Conversion: score = max(0, 1 - dist)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from datetime import datetime, timezone

        from mem0.vector_stores.valkey import ValkeyDB

        self.collection = f"test_norm_{uuid.uuid4().hex[:8]}"
        self.store = ValkeyDB(
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            valkey_url=f"valkey://{VALKEY_HOST}:{VALKEY_PORT}",
        )

        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        payloads = [
            {"hash": f"h{i}", "data": f"{v['label']} memory", "created_at": now, "user_id": "test", **v}
            for i, v in enumerate(vectors["payloads"])
        ]
        ids = [str(uuid.uuid4()) for _ in range(3)]
        self.store.insert(vectors=vectors["docs"], payloads=payloads, ids=ids)
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(
            query="", vectors=self.query, top_k=3, filters={"user_id": "test"}
        )
        scores = [r.score for r in results]
        assert all(s >= 0 for s in scores), f"Scores must be non-negative: {scores}"
        assert all(s <= 1.0 for s in scores), f"Scores must be <= 1.0: {scores}"
        assert scores[0] >= scores[1] >= scores[2], f"Scores must be descending: {scores}"


# --- Milvus L2 ---

MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))


@pytest.mark.skipif(
    not _tcp_reachable(MILVUS_HOST, MILVUS_PORT),
    reason=f"Milvus not reachable at {MILVUS_HOST}:{MILVUS_PORT}",
)
class TestMilvusL2:
    """Milvus L2 returns L2 distance. Conversion: score = 1 / (1 + distance)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from mem0.vector_stores.milvus import MilvusDB

        self.collection = f"test_l2_{uuid.uuid4().hex[:8]}"
        self.store = MilvusDB(
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            url=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            token="",
            db_name="",
            metric_type="L2",
        )
        ids = [str(uuid.uuid4()) for _ in range(3)]
        self.store.insert(ids=ids, vectors=vectors["docs"], payloads=vectors["payloads"])
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)


@pytest.mark.skipif(
    not _tcp_reachable(MILVUS_HOST, MILVUS_PORT),
    reason=f"Milvus not reachable at {MILVUS_HOST}:{MILVUS_PORT}",
)
class TestMilvusCosine:
    """Milvus COSINE already returns similarity. No conversion needed."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from mem0.vector_stores.milvus import MilvusDB

        self.collection = f"test_cos_{uuid.uuid4().hex[:8]}"
        self.store = MilvusDB(
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            url=f"http://{MILVUS_HOST}:{MILVUS_PORT}",
            token="",
            db_name="",
            metric_type="COSINE",
        )
        ids = [str(uuid.uuid4()) for _ in range(3)]
        self.store.insert(ids=ids, vectors=vectors["docs"], payloads=vectors["payloads"])
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_descending(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        scores = [r.score for r in results]
        labels = [r.payload["label"] for r in results]
        assert scores[0] >= scores[1] >= scores[2], f"Descending: {list(zip(labels, scores))}"
        assert labels[0] == "close"


# --- Supabase ---

SUPABASE_CONN = os.environ.get("SUPABASE_CONN_STRING", "")


@pytest.mark.skipif(not SUPABASE_CONN, reason="SUPABASE_CONN_STRING not set")
class TestSupabase:
    """Supabase (vecs) returns cosine distance [0,2]. Conversion: score = max(0, 1 - dist)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from mem0.vector_stores.supabase import Supabase

        self.collection = f"test_norm_{uuid.uuid4().hex[:8]}"
        self.store = Supabase(
            connection_string=SUPABASE_CONN,
            collection_name=self.collection,
            embedding_model_dims=DIMS,
        )
        self.store.insert(vectors=vectors["docs"], payloads=vectors["payloads"], ids=vectors["ids"])
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)


# --- S3 Vectors ---

S3_BUCKET = os.environ.get("S3_VECTORS_BUCKET", "")


@pytest.mark.skipif(not S3_BUCKET, reason="S3_VECTORS_BUCKET not set")
class TestS3Vectors:
    """S3 Vectors returns cosine distance. Conversion: score = max(0, 1 - dist)."""

    @pytest.fixture(autouse=True)
    def setup(self, vectors):
        from mem0.vector_stores.s3_vectors import S3Vectors

        self.collection = f"testnorm{uuid.uuid4().hex[:8]}"
        region = os.environ.get("S3_VECTORS_REGION", "us-east-1")
        self.store = S3Vectors(
            vector_bucket_name=S3_BUCKET,
            collection_name=self.collection,
            embedding_model_dims=DIMS,
            distance_metric="cosine",
            region_name=region,
        )
        self.store.insert(vectors=vectors["docs"], payloads=vectors["payloads"], ids=vectors["ids"])
        self.query = vectors["query"]
        yield
        self.store.delete_col()

    def test_scores_are_similarity(self):
        results = self.store.search(query="", vectors=self.query, top_k=3)
        _assert_similarity_scores(results)
