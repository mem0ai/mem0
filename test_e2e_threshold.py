"""
Level 2: End-to-end test for Memory.search(threshold=...) across vector stores.
Tests the full pipeline: Memory.add() -> Memory.search(threshold=X) -> verify filtering.
Uses Ollama LLM (llama3.2) + Ollama embeddings (nomic-embed-text).
"""
import sys
import os
import shutil
import time
import logging

logging.basicConfig(level=logging.WARNING)
# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

EMBED_DIMS = 768  # nomic-embed-text

def get_base_config(vector_store_provider, vector_store_config):
    """Build a MemoryConfig dict for the given vector store."""
    return {
        "llm": {
            "provider": "ollama",
            "config": {
                "model": "llama3.2",
                "ollama_base_url": "http://localhost:11434",
                "temperature": 0.0,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": "http://localhost:11434",
            },
        },
        "vector_store": {
            "provider": vector_store_provider,
            "config": vector_store_config,
        },
    }


def run_threshold_test(provider_name, config_dict):
    """
    Core e2e test: add memories, search with threshold, verify filtering works.
    Returns True if passed, raises on failure.
    """
    from mem0 import Memory

    print(f"\n{'='*50}")
    print(f"Level 2 E2E: {provider_name}")
    print(f"{'='*50}")

    m = Memory.from_config(config_dict)

    user_id = f"test_threshold_{provider_name}_{int(time.time())}"

    # Step 1: Add diverse memories
    print("  Adding memories...")
    memories_to_add = [
        "I love playing tennis every weekend at the local club",
        "My favorite programming language is Python and I use it daily",
        "I have a golden retriever named Max who is 3 years old",
        "I work as a machine learning engineer at a tech startup",
        "My favorite food is sushi, especially salmon nigiri",
    ]
    for mem_text in memories_to_add:
        result = m.add(mem_text, user_id=user_id)
        if result.get("results"):
            print(f"    Added: {result['results'][0].get('memory', mem_text[:40])}")

    # Step 2: Search WITHOUT threshold (baseline)
    print("\n  Searching without threshold (baseline)...")
    results_no_threshold = m.search("What programming language do I use?", user_id=user_id)
    baseline_results = results_no_threshold.get("results", [])
    print(f"    Got {len(baseline_results)} results:")
    for r in baseline_results:
        print(f"      score={r.get('score', 'N/A'):.4f}  {r.get('memory', '?')[:60]}")

    if not baseline_results:
        raise RuntimeError("No results returned without threshold - something is wrong")

    # Step 3: Search WITH a high threshold - should filter out irrelevant results
    scores = [r["score"] for r in baseline_results if r.get("score") is not None]
    if not scores:
        raise RuntimeError("No scores in results")

    # Verify scores are similarity (higher = better): top result should have highest score
    assert scores[0] >= scores[-1], \
        f"Scores should be descending (higher=better), got first={scores[0]}, last={scores[-1]}"

    # Use a threshold between the best and worst score
    if len(scores) >= 2:
        threshold = (scores[0] + scores[1]) / 2  # between top 2
    else:
        threshold = scores[0] * 0.9

    print(f"\n  Searching WITH threshold={threshold:.4f}...")
    results_with_threshold = m.search(
        "What programming language do I use?",
        user_id=user_id,
        threshold=threshold,
    )
    filtered_results = results_with_threshold.get("results", [])
    print(f"    Got {len(filtered_results)} results (filtered from {len(baseline_results)}):")
    for r in filtered_results:
        print(f"      score={r.get('score', 'N/A'):.4f}  {r.get('memory', '?')[:60]}")

    # Step 4: Verify threshold filtering
    # All returned results should have score >= threshold
    for r in filtered_results:
        s = r.get("score")
        if s is not None:
            assert s >= threshold, \
                f"Result with score {s:.4f} should not pass threshold {threshold:.4f}"

    # Should have fewer results than baseline (threshold filtered some out)
    assert len(filtered_results) <= len(baseline_results), \
        "Threshold filtering should not return MORE results"

    # Step 5: Very high threshold should return very few or no results
    print("\n  Searching WITH very high threshold=0.99...")
    results_high = m.search(
        "What programming language do I use?",
        user_id=user_id,
        threshold=0.99,
    )
    high_filtered = results_high.get("results", [])
    print(f"    Got {len(high_filtered)} results")
    for r in high_filtered:
        assert r.get("score", 0) >= 0.99, \
            f"Score {r.get('score')} below 0.99 threshold"

    print(f"\n  ✓ {provider_name} Level 2 E2E PASSED!")
    return True


# ============================================================
# Per-store configs
# ============================================================

def test_faiss_e2e():
    path = "/tmp/mem0_e2e_faiss"
    shutil.rmtree(path, ignore_errors=True)
    config = get_base_config("faiss", {
        "collection_name": "e2e_faiss_test",
        "path": path,
        "distance_strategy": "euclidean",
        "embedding_model_dims": EMBED_DIMS,
    })
    result = run_threshold_test("FAISS (euclidean)", config)
    shutil.rmtree(path, ignore_errors=True)
    return result


def test_chroma_e2e():
    config = get_base_config("chroma", {
        "collection_name": "e2e_chroma_test",
        "path": "/tmp/mem0_e2e_chroma",
    })
    result = run_threshold_test("ChromaDB", config)
    shutil.rmtree("/tmp/mem0_e2e_chroma", ignore_errors=True)
    return result


def test_pgvector_e2e():
    config = get_base_config("pgvector", {
        "collection_name": "e2e_pgvector_test",
        "embedding_model_dims": EMBED_DIMS,
        "host": "localhost",
        "port": 5432,
        "user": "mem0",
        "password": "mem0test",
        "dbname": "mem0_test",
        "diskann": False,
        "hnsw": True,
    })
    return run_threshold_test("PGVector", config)


def test_redis_e2e():
    config = get_base_config("redis", {
        "collection_name": "e2e_redis_test",
        "embedding_model_dims": EMBED_DIMS,
        "redis_url": "redis://localhost:6379",
    })
    return run_threshold_test("Redis", config)


def test_valkey_e2e():
    config = get_base_config("valkey", {
        "collection_name": "e2e_valkey_test",
        "embedding_model_dims": EMBED_DIMS,
        "valkey_url": "valkey://localhost:6380",
    })
    return run_threshold_test("Valkey", config)


def test_milvus_l2_e2e():
    config = get_base_config("milvus", {
        "collection_name": "e2e_milvus_l2_test",
        "embedding_model_dims": EMBED_DIMS,
        "url": "http://localhost:19530",
        "token": "",
        "metric_type": "L2",
    })
    return run_threshold_test("Milvus (L2)", config)


def test_milvus_cosine_e2e():
    config = get_base_config("milvus", {
        "collection_name": "e2e_milvus_cos_test",
        "embedding_model_dims": EMBED_DIMS,
        "url": "http://localhost:19530",
        "token": "",
        "metric_type": "COSINE",
    })
    return run_threshold_test("Milvus (COSINE)", config)


def test_cassandra_e2e():
    config = get_base_config("cassandra", {
        "collection_name": "e2e_cassandra_test",
        "embedding_model_dims": EMBED_DIMS,
        "contact_points": ["localhost"],
        "port": 9042,
        "keyspace": "mem0_e2e",
    })
    return run_threshold_test("Cassandra", config)


def test_s3_vectors_e2e():
    config = get_base_config("s3_vectors", {
        "vector_bucket_name": "mem0-e2e-test",
        "collection_name": "e2es3vtest",
        "embedding_model_dims": EMBED_DIMS,
        "distance_metric": "cosine",
        "region_name": "us-east-1",
    })
    return run_threshold_test("S3 Vectors", config)


def test_supabase_e2e():
    conn_str = os.environ.get("SUPABASE_CONN_STRING", "")
    if not conn_str:
        raise RuntimeError("SUPABASE_CONN_STRING env var not set")
    config = get_base_config("supabase", {
        "connection_string": conn_str,
        "collection_name": "e2e_supabase_test",
        "embedding_model_dims": EMBED_DIMS,
    })
    return run_threshold_test("Supabase", config)


# ============================================================
# Runner
# ============================================================

if __name__ == "__main__":
    test_name = sys.argv[1] if len(sys.argv) > 1 else "faiss"

    tests = {
        "faiss": test_faiss_e2e,
        "chroma": test_chroma_e2e,
        "pgvector": test_pgvector_e2e,
        "redis": test_redis_e2e,
        "valkey": test_valkey_e2e,
        "milvus_l2": test_milvus_l2_e2e,
        "milvus_cosine": test_milvus_cosine_e2e,
        "cassandra": test_cassandra_e2e,
        "s3_vectors": test_s3_vectors_e2e,
        "supabase": test_supabase_e2e,
    }

    if test_name == "all":
        to_run = tests
    elif test_name in tests:
        to_run = {test_name: tests[test_name]}
    else:
        print(f"Unknown test: {test_name}")
        print(f"Available: {', '.join(tests.keys())}, all")
        sys.exit(1)

    passed = 0
    failed = 0

    for name, test_fn in to_run.items():
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"\n  ✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Level 2 E2E Results: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
