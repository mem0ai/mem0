# SPDX-License-Identifier: Apache-2.0
"""Zero-Mock unit test suite for the Mem0 Silicium vector store backend (``SiliciumDB`` & ``SiliciumConfig``)."""

import math
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent

try:
    from mem0.configs.vector_stores.silicium import SiliciumConfig
    from mem0.vector_stores.silicium import (
        _COLLECTION_ARENA,
        _MAX_TENANT_SCOPES,
        _MAX_VECTOR_DIM,
        OutputData,
        SiliciumDB,
    )
except Exception:
    import importlib.util

    _cfg_path = _THIS_DIR / "mem0_silicium_config.py"
    if not _cfg_path.is_file():
        _cfg_path = _THIS_DIR.parents[1] / "mem0" / "configs" / "vector_stores" / "silicium.py"
    _spec_cfg = importlib.util.spec_from_file_location("mem0.configs.vector_stores.silicium", _cfg_path)
    assert _spec_cfg is not None and _spec_cfg.loader is not None
    _mod_cfg = importlib.util.module_from_spec(_spec_cfg)
    sys.modules["mem0.configs.vector_stores.silicium"] = _mod_cfg
    _spec_cfg.loader.exec_module(_mod_cfg)
    SiliciumConfig = _mod_cfg.SiliciumConfig

    _vs_path = _THIS_DIR / "mem0_silicium_vector_store.py"
    if not _vs_path.is_file():
        _vs_path = _THIS_DIR.parents[1] / "mem0" / "vector_stores" / "silicium.py"
    _spec_vs = importlib.util.spec_from_file_location("mem0.vector_stores.silicium", _vs_path)
    assert _spec_vs is not None and _spec_vs.loader is not None
    _mod_vs = importlib.util.module_from_spec(_spec_vs)
    sys.modules["mem0.vector_stores.silicium"] = _mod_vs
    _spec_vs.loader.exec_module(_mod_vs)
    _COLLECTION_ARENA = _mod_vs._COLLECTION_ARENA
    _MAX_TENANT_SCOPES = _mod_vs._MAX_TENANT_SCOPES
    _MAX_VECTOR_DIM = _mod_vs._MAX_VECTOR_DIM
    OutputData = _mod_vs.OutputData
    SiliciumDB = _mod_vs.SiliciumDB


def _normalize_bm25_sigmoid(raw_score: float, midpoint: float = 5.0, steepness: float = 0.7) -> float:
    """Reference logistic sigmoid matching ``mem0.utils.scoring.normalize_bm25``."""
    return 1.0 / (1.0 + math.exp(-steepness * (raw_score - midpoint)))


def test_silicium_config_validation_and_annotations() -> None:
    """Verify ``SiliciumConfig`` validation, extra field rejection, and ``path`` annotation presence."""
    assert "path" in SiliciumConfig.__annotations__

    cfg = SiliciumConfig(
        collection_name="agent_mem",
        embedding_model_dims=128,
        distance_strategy="COSINE",
        max_tenant_scopes=64,
    )
    assert cfg.collection_name == "agent_mem"
    assert cfg.embedding_model_dims == 128
    assert cfg.distance_strategy == "cosine"
    assert cfg.max_tenant_scopes == 64

    with pytest.raises(ValueError, match="Invalid distance_strategy"):
        SiliciumConfig(distance_strategy="manhattan_invalid")

    with pytest.raises(ValueError, match="embedding_model_dims"):
        SiliciumConfig(embedding_model_dims=0)

    with pytest.raises(ValueError, match="embedding_model_dims"):
        SiliciumConfig(embedding_model_dims=_MAX_VECTOR_DIM + 1)

    with pytest.raises(ValueError, match="max_tenant_scopes"):
        SiliciumConfig(max_tenant_scopes=_MAX_TENANT_SCOPES + 1)

    with pytest.raises(ValueError, match="Extra fields not allowed"):
        SiliciumConfig(**{"collection_name": "mem0", "unknown_field": 123})  # type: ignore[arg-type]


def test_silicium_crud_and_score_normalization_three_strategies() -> None:
    """Verify CRUD operations, ``update`` False/True contract, and score normalization across all 3 metrics."""
    _COLLECTION_ARENA.clear()

    query_vec = [1.0, 0.0, 0.0, 0.0]
    close_vec = [0.98, 0.19, 0.0, 0.0]
    mid_vec = [0.70, 0.71, 0.0, 0.0]
    far_vec = [0.0, 1.0, 0.0, 0.0]

    for strategy in ("cosine", "euclidean", "inner_product"):
        store = SiliciumDB(
            collection_name=f"norm_{strategy}",
            embedding_model_dims=4,
            distance_strategy=strategy,
        )
        assert store.engine_backend in ("silicium_c_abi_simd", "python_portable_fallback")

        store.insert(
            vectors=[close_vec, mid_vec, far_vec],
            payloads=[
                {"label": "close", "user_id": "u1", "data": "python vector store fast search"},
                {"label": "mid", "user_id": "u1", "data": "python memory layer"},
                {"label": "far", "user_id": "u2", "data": "unrelated topic"},
            ],
            ids=["id_close", "id_mid", "id_far"],
        )

        hits = store.search(query="", vectors=query_vec, top_k=3)
        assert len(hits) == 3
        assert isinstance(hits[0], OutputData)
        scores = [float(r.score or 0.0) for r in hits]
        assert scores[0] >= scores[1] >= scores[2]
        assert hits[0].id == "id_close"

        if strategy in ("cosine", "euclidean"):
            assert all(0.0 <= s <= 1.0 for s in scores)

        # Update contract: non-existent ID returns False and never creates a ghost record
        assert store.update("non_existent_id", payload={"ghost": True}) is False
        assert store.get("non_existent_id") is None

        assert store.update("id_mid", payload={"label": "mid_updated", "user_id": "u1"}) is True
        fetched = store.get("id_mid")
        assert fetched is not None
        assert fetched.payload is not None
        assert fetched.payload["label"] == "mid_updated"

        # List returns [results] for _vector_store_list_rows compatibility
        listed = store.list(filters={"user_id": "u1"}, top_k=10)
        assert isinstance(listed, list) and len(listed) == 1
        assert len(listed[0]) == 2

        info = store.col_info()
        assert info["count"] == 3
        assert info["dimension"] == 4

        store.delete("id_far")
        assert store.get("id_far") is None
        store.delete_col()


def test_silicium_search_batch_and_bm25_keyword_search() -> None:
    """Verify native 1-pass ``search_batch`` and Okapi BM25 ``keyword_search`` calibration."""
    _COLLECTION_ARENA.clear()
    store = SiliciumDB(collection_name="hybrid_mem", embedding_model_dims=4, distance_strategy="cosine")

    store.insert(
        vectors=[
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        payloads=[
            {
                "user_id": "alice",
                "data": "Silicium vector store accelerates batch entity deduplication",
                "text_lemmatized": "silicium vector store accelerate batch entity deduplication",
            },
            {
                "user_id": "alice",
                "data": "Hybrid retrieval combines semantic embeddings and BM25 lexical scoring",
                "text_lemmatized": "hybrid retrieval combine semantic embedding bm25 lexical score",
            },
            {
                "user_id": "bob",
                "data": "Silicium vector store isolated tenant scope",
                "text_lemmatized": "silicium vector store isolate tenant scope",
            },
        ],
        ids=["m1", "m2", "m3"],
    )

    # 1. Native search_batch with shared metadata filter
    batch_hits = store.search_batch(
        queries=["entity one", "entity two"],
        vectors_list=[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        top_k=1,
        filters={"user_id": "alice"},
    )
    assert len(batch_hits) == 2
    assert len(batch_hits[0]) == 1 and batch_hits[0][0].id == "m1"
    assert len(batch_hits[1]) == 1 and batch_hits[1][0].id == "m2"

    # 2. Native keyword_search calibrated for mem0.utils.scoring.normalize_bm25 (midpoint=5.0, steepness=0.7)
    kw_hits = store.keyword_search(
        query="silicium vector store",
        top_k=5,
        filters={"user_id": "alice"},
    )
    assert len(kw_hits) == 1
    assert kw_hits[0].id == "m1"
    raw_bm25 = float(kw_hits[0].score or 0.0)
    assert raw_bm25 >= 5.0
    assert _normalize_bm25_sigmoid(raw_bm25) >= 0.5


def test_silicium_advanced_metadata_filters_and_adversarial_operators() -> None:
    """Verify logical operators (``AND``, ``OR``, ``NOT``), range/ISO-8601 comparisons, and invalid operator errors."""
    _COLLECTION_ARENA.clear()
    store = SiliciumDB(collection_name="filter_mem", embedding_model_dims=4)
    store.insert(
        vectors=[[1.0, 0.0, 0.0, 0.0], [0.9, 0.1, 0.0, 0.0], [0.8, 0.2, 0.0, 0.0]],
        payloads=[
            {
                "user_id": "u1",
                "priority": 10,
                "tags": "urgent_backend",
                "expiration_date": "2027-06-01T00:00:00Z",
            },
            {
                "user_id": "u1",
                "priority": 3,
                "tags": "low_frontend",
                "expiration_date": "2025-01-01T00:00:00Z",
            },
            {
                "user_id": "u2",
                "priority": 8,
                "tags": "urgent_ops",
                "expiration_date": "2027-12-31T00:00:00Z",
            },
        ],
        ids=["f1", "f2", "f3"],
    )

    complex_filter: dict[str, object] = {
        "AND": [
            {"user_id": ["u1", "u2"]},
            {"priority": {"gte": 5}},
            {"expiration_date": {"gt": "2026-01-01T00:00:00Z"}},
            {"NOT": [{"user_id": "u2"}]},
            {"tags": {"icontains": "URGENT"}},
        ]
    }
    res = store.search(query="", vectors=[1.0, 0.0, 0.0, 0.0], top_k=5, filters=complex_filter)
    assert [r.id for r in res] == ["f1"]

    with pytest.raises(ValueError, match="Unsupported filter operator"):
        store.search(query="", vectors=[1.0, 0.0, 0.0, 0.0], filters={"priority": {"$regex": ".*"}})

    with pytest.raises(ValueError, match="Cannot mix range operators"):
        store.search(query="", vectors=[1.0, 0.0, 0.0, 0.0], filters={"priority": {"gt": 1, "eq": 5}})

    with pytest.raises(ValueError, match="must be a list"):
        store.search(query="", vectors=[1.0, 0.0, 0.0, 0.0], filters={"AND": {"user_id": "u1"}})


def test_silicium_multi_collection_directory_persistence_and_factory() -> None:
    """Verify multi-collection directory persistence (``mem0``, ``mem0_entities``, ``mem0migrations``) on 4 threads."""
    _COLLECTION_ARENA.clear()
    with tempfile.TemporaryDirectory() as tmp_dir:
        shared_dir = str(Path(tmp_dir) / "silicium_shared")
        col_names = ["mem0", "mem0_entities", "mem0migrations"]

        def _worker(col_name: str) -> str:
            db = SiliciumDB(collection_name=col_name, embedding_model_dims=4, path=shared_dir)
            db.insert(
                vectors=[[1.0, 0.0, 0.0, 0.0]],
                payloads=[{"collection": col_name, "user_id": "u1"}],
                ids=[f"id_{col_name}"],
            )
            return col_name

        with ThreadPoolExecutor(max_workers=4) as pool:
            completed = list(pool.map(_worker, col_names))
        assert completed == col_names

        # Clear RAM arena and verify reload from per-collection JSON files in shared_dir
        _COLLECTION_ARENA.clear()
        for col_name in col_names:
            reloaded = SiliciumDB(collection_name=col_name, embedding_model_dims=4, path=shared_dir)
            rec = reloaded.get(f"id_{col_name}")
            assert rec is not None and rec.payload is not None
            assert rec.payload["collection"] == col_name

        try:
            from mem0.utils.factory import VectorStoreFactory
            from mem0.vector_stores.configs import VectorStoreConfig

            if "silicium" in VectorStoreConfig._provider_configs:
                vs_cfg = VectorStoreConfig(
                    provider="silicium",
                    config={"collection_name": "factory_col", "embedding_model_dims": 4, "path": shared_dir},
                )
                instance = VectorStoreFactory.create("silicium", vs_cfg.config)
                assert isinstance(instance, SiliciumDB)
        except ImportError:
            pass


if __name__ == "__main__":
    test_silicium_config_validation_and_annotations()
    test_silicium_crud_and_score_normalization_three_strategies()
    test_silicium_search_batch_and_bm25_keyword_search()
    test_silicium_advanced_metadata_filters_and_adversarial_operators()
    test_silicium_multi_collection_directory_persistence_and_factory()
