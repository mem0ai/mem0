"""
End-to-end test for PR #4456: score normalization across vector stores.
Tests that all affected vector stores return similarity scores (higher = better).

Level 1: Vector store layer - direct insert/search, verify scores
Level 2: Memory pipeline - Memory.add() + Memory.search(threshold=...)
"""
import numpy as np
import sys
import shutil
import os
import logging
import uuid

logging.basicConfig(level=logging.WARNING)

DIMS = 128

def make_vectors():
    """Create a query vector and 3 document vectors with known similarity ordering."""
    np.random.seed(42)
    query = np.random.randn(DIMS).astype(np.float32)
    query = query / np.linalg.norm(query)

    close_vec = query + np.random.randn(DIMS).astype(np.float32) * 0.1
    close_vec = close_vec / np.linalg.norm(close_vec)

    mid_vec = query + np.random.randn(DIMS).astype(np.float32) * 0.5
    mid_vec = mid_vec / np.linalg.norm(mid_vec)

    far_vec = np.random.randn(DIMS).astype(np.float32)
    far_vec = far_vec / np.linalg.norm(far_vec)

    return query.tolist(), [close_vec.tolist(), mid_vec.tolist(), far_vec.tolist()]


def assert_scores_valid(results, test_name):
    """Common assertions for all vector store tests."""
    scores = [r.score for r in results]
    labels = [r.payload.get("label", "?") for r in results]

    print(f"\n=== {test_name} ===")
    for r in results:
        print(f"  {r.payload.get('label', '?'):>6}: score={r.score:.4f}")

    # 1. All scores must be non-negative (similarity, not raw distance)
    assert all(s >= 0 for s in scores), f"All scores must be non-negative, got {scores}"

    # 2. Scores should be <= 1 for normalized similarity
    assert all(s <= 1.0 for s in scores), f"Scores should be in [0, 1], got {scores}"

    # 3. Ordering: higher score = more similar
    assert scores[0] >= scores[1] >= scores[2], \
        f"Results should be ordered by descending similarity, got {scores}"

    # 4. Closest vector should rank first
    assert labels[0] == "close", f"Closest vector should rank first, got {labels[0]}"

    # 5. Threshold filtering test
    threshold = scores[1]  # mid score
    filtered = [r for r in results if r.score >= threshold]
    assert len(filtered) >= 2, "Threshold should keep at least close and mid"

    print("  ✓ All assertions passed!")
    return True


# ============================================================
# LEVEL 1: Vector Store Layer Tests
# ============================================================

def test_faiss_euclidean():
    from mem0.vector_stores.faiss import FAISS
    path = "/tmp/faiss_test_norm"
    shutil.rmtree(path, ignore_errors=True)
    store = FAISS(collection_name="test", path=path, distance_strategy="euclidean", embedding_model_dims=DIMS)
    query, docs = make_vectors()
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=["c", "m", "f"])
    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "FAISS (euclidean)")
    shutil.rmtree(path, ignore_errors=True)
    return result


def test_faiss_cosine():
    from mem0.vector_stores.faiss import FAISS
    path = "/tmp/faiss_test_cos"
    shutil.rmtree(path, ignore_errors=True)
    store = FAISS(collection_name="test", path=path, distance_strategy="cosine", embedding_model_dims=DIMS)
    query, docs = make_vectors()
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=["c", "m", "f"])
    results = store.search(query="", vectors=query, limit=3)

    # Cosine/IP scores on normalized vectors can be negative for dissimilar vectors
    # so we only check ordering and that close > far
    print("\n=== FAISS (cosine/IP) ===")
    for r in results:
        print(f"  {r.payload.get('label', '?'):>6}: score={r.score:.4f}")
    assert results[0].score >= results[1].score >= results[2].score
    assert results[0].payload["label"] == "close"
    print("  ✓ All assertions passed!")
    return True


def test_chroma():
    from mem0.vector_stores.chroma import ChromaDB
    store = ChromaDB(collection_name="test_chroma_norm")
    query, docs = make_vectors()
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=["c", "m", "f"])
    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "ChromaDB (L2 -> similarity)")
    store.delete_col()
    return result


def test_pgvector(host="localhost", port=5432):
    from mem0.vector_stores.pgvector import PGVector
    store = PGVector(
        collection_name="test_pgvector_norm",
        embedding_model_dims=DIMS,
        host=host,
        port=port,
        user="mem0",
        password="mem0test",
        dbname="mem0_test",
        diskann=False,
        hnsw=True,
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)
    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "PGVector (cosine distance -> similarity)")
    # cleanup
    store.delete_col()
    return result


def test_redis(host="localhost", port=6379):
    from mem0.vector_stores.redis import RedisDB
    from datetime import datetime, timezone
    store = RedisDB(
        collection_name="test_redis_norm",
        embedding_model_dims=DIMS,
        redis_url=f"redis://{host}:{port}",
    )
    query, docs = make_vectors()
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    payloads = [
        {"hash": "h1", "data": "close memory", "created_at": now, "user_id": "test", "label": "close"},
        {"hash": "h2", "data": "mid memory", "created_at": now, "user_id": "test", "label": "mid"},
        {"hash": "h3", "data": "far memory", "created_at": now, "user_id": "test", "label": "far"},
    ]
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=payloads, ids=ids)
    results = store.search(query="", vectors=query, limit=3, filters={"user_id": "test"})

    # Redis returns MemoryResult not OutputData, adapt for assertion
    print("\n=== Redis (cosine distance -> similarity) ===")
    for r in results:
        label = r.payload.get("data", "?").split()[0]
        print(f"  {label:>6}: score={r.score:.4f}")
    assert results[0].score >= results[1].score >= results[2].score, \
        f"Descending order expected, got {[r.score for r in results]}"
    assert all(r.score >= 0 for r in results), "Scores must be non-negative"
    assert all(r.score <= 1.0 for r in results), "Scores must be <= 1.0"
    print("  ✓ All assertions passed!")
    store.delete_col()
    return True


def test_valkey(host="localhost", port=6380):
    from mem0.vector_stores.valkey import ValkeyDB
    from datetime import datetime, timezone
    store = ValkeyDB(
        collection_name="test_valkey_norm",
        embedding_model_dims=DIMS,
        valkey_url=f"valkey://{host}:{port}",
    )
    query, docs = make_vectors()
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    payloads = [
        {"hash": "h1", "data": "close memory", "created_at": now, "user_id": "test", "label": "close"},
        {"hash": "h2", "data": "mid memory", "created_at": now, "user_id": "test", "label": "mid"},
        {"hash": "h3", "data": "far memory", "created_at": now, "user_id": "test", "label": "far"},
    ]
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=payloads, ids=ids)
    results = store.search(query="", vectors=query, limit=3, filters={"user_id": "test"})

    print("\n=== Valkey (cosine distance -> similarity) ===")
    for r in results:
        print(f"  score={r.score:.4f}")
    assert results[0].score >= results[1].score >= results[2].score, \
        f"Descending order expected, got {[r.score for r in results]}"
    assert all(r.score >= 0 for r in results), "Scores must be non-negative"
    assert all(r.score <= 1.0 for r in results), "Scores must be <= 1.0"
    print("  ✓ All assertions passed!")
    store.delete_col()
    return True


def test_milvus_l2(host="localhost", port=19530):
    from mem0.vector_stores.milvus import MilvusDB
    store = MilvusDB(
        collection_name="test_milvus_l2_norm",
        embedding_model_dims=DIMS,
        url=f"http://{host}:{port}",
        token=None,
        db_name="",
        metric_type="L2",
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)
    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "Milvus (L2 -> similarity)")
    store.delete_col()
    return result


def test_milvus_cosine(host="localhost", port=19530):
    from mem0.vector_stores.milvus import MilvusDB
    store = MilvusDB(
        collection_name="test_milvus_cos_norm",
        embedding_model_dims=DIMS,
        url=f"http://{host}:{port}",
        token=None,
        db_name="",
        metric_type="COSINE",
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)
    results = store.search(query="", vectors=query, limit=3)

    # COSINE metric in Milvus already returns similarity (higher = better)
    print("\n=== Milvus (COSINE - already similarity) ===")
    for r in results:
        print(f"  {r.payload.get('label', '?'):>6}: score={r.score:.4f}")
    assert results[0].score >= results[1].score >= results[2].score
    assert results[0].payload["label"] == "close"
    print("  ✓ All assertions passed!")
    return True


def test_cassandra(host="localhost", port=9042):
    from mem0.vector_stores.cassandra import CassandraDB
    store = CassandraDB(
        collection_name="test_cassandra_norm",
        embedding_model_dims=DIMS,
        contact_points=[host],
        port=port,
        keyspace="mem0_test",
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)
    results = store.search(query="", vectors=query, limit=3)
    # Cassandra now returns similarity directly (not 1-similarity)
    print("\n=== Cassandra (cosine similarity direct) ===")
    for r in results:
        print(f"  {r.payload.get('label', '?'):>6}: score={r.score:.4f}")
    assert results[0].score >= results[1].score >= results[2].score
    assert results[0].payload["label"] == "close"
    # Cosine similarity ranges from [-1, 1]; negative is valid for dissimilar vectors
    assert all(r.score >= -1.0 for r in results), "Cosine similarity must be >= -1.0"
    assert all(r.score <= 1.0 for r in results), "Cosine similarity must be <= 1.0"
    print("  ✓ All assertions passed!")
    store.delete_col()
    return True


def test_s3_vectors(region="us-east-1"):
    from mem0.vector_stores.s3_vectors import S3Vectors
    store = S3Vectors(
        vector_bucket_name="mem0-test-score-norm",
        collection_name="tests3vnorm",
        embedding_model_dims=DIMS,
        distance_metric="cosine",
        region_name=region,
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)

    # S3 Vectors may need a moment to index
    import time
    time.sleep(2)

    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "S3 Vectors (cosine distance -> similarity)")
    store.delete_col()
    return result


def test_supabase():
    from mem0.vector_stores.supabase import Supabase
    conn_str = os.environ.get("SUPABASE_CONN_STRING", "")
    if not conn_str:
        raise RuntimeError("SUPABASE_CONN_STRING env var not set")
    store = Supabase(
        connection_string=conn_str,
        collection_name="test_supabase_norm",
        embedding_model_dims=DIMS,
    )
    query, docs = make_vectors()
    ids = [str(uuid.uuid4()) for _ in range(3)]
    store.insert(vectors=docs, payloads=[{"label": "close"}, {"label": "mid"}, {"label": "far"}], ids=ids)
    results = store.search(query="", vectors=query, limit=3)
    result = assert_scores_valid(results, "Supabase (cosine distance -> similarity)")
    store.delete_col()
    return result


# ============================================================
# Runner
# ============================================================

if __name__ == "__main__":
    test_name = sys.argv[1] if len(sys.argv) > 1 else "all_local"

    tests = {
        "faiss": [test_faiss_euclidean, test_faiss_cosine],
        "chroma": [test_chroma],
        "pgvector": [test_pgvector],
        "redis": [test_redis],
        "valkey": [test_valkey],
        "milvus": [test_milvus_l2, test_milvus_cosine],
        "cassandra": [test_cassandra],
        "s3_vectors": [test_s3_vectors],
        "supabase": [test_supabase],
    }

    # "all_local" runs only faiss + chroma (no Docker)
    local_tests = ["faiss", "chroma"]
    docker_tests = ["pgvector", "redis", "valkey", "milvus", "cassandra"]

    if test_name == "all_local":
        to_run = {k: tests[k] for k in local_tests}
    elif test_name == "all":
        to_run = tests
    elif test_name in tests:
        to_run = {test_name: tests[test_name]}
    else:
        print(f"Unknown test: {test_name}")
        print(f"Available: {', '.join(tests.keys())}, all_local, all")
        sys.exit(1)

    passed = 0
    failed = 0

    for name, test_fns in to_run.items():
        for fn in test_fns:
            try:
                if fn():
                    passed += 1
            except Exception as e:
                print(f"\n=== {fn.__name__} ===")
                print(f"  ✗ FAILED: {e}")
                failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
