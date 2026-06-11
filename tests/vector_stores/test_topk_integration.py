"""
Integration tests for TopK — hit a real TopK endpoint.

Requires env vars:
  TOPK_API_KEY   — API key
  TOPK_REGION    — region
  TOPK_HOST      — optional host override
  TOPK_HTTPS     — optional, defaults to True

Run:
  pytest tests/vector_stores/test_topk_integration.py -v
"""

import os
import uuid

import pytest

pytest.importorskip("topk_sdk", reason="topk-sdk not installed")

from mem0.vector_stores.topk import TopK

# Skip the entire module if TOPK_API_KEY or TOPK_REGION are not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("TOPK_API_KEY") or not os.environ.get("TOPK_REGION"),
    reason="TOPK_API_KEY and TOPK_REGION must be set",
)

DIMS = 8
COLLECTION = f"mem0-integration-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def db():
    store = TopK(
        collection_name=COLLECTION,
        embedding_model_dims=DIMS,
    )
    yield store
    store.delete_col()


def _vec(seed: float) -> list:
    import math

    v = [math.sin(seed + i) for i in range(DIMS)]
    norm = sum(x**2 for x in v) ** 0.5
    return [x / norm for x in v]


def _payload(text: str, user_id: str, **extra) -> dict:
    """Build a minimal Mem0-compatible payload."""
    return {
        "data": text,
        "hash": str(hash(text)),
        "text_lemmatized": text.lower(),
        "user_id": user_id,
        **extra,
    }


class TestIntegration:
    def test_col_info(self, db):
        info = db.col_info()
        assert info["name"] == COLLECTION

    def test_insert_and_get(self, db):
        vec = _vec(1.0)
        db.insert([vec], [_payload("I love sci-fi", "alice")], ["doc1"])

        result = db.get("doc1")
        assert result is not None
        assert result.id == "doc1"
        assert result.payload.get("data") == "I love sci-fi"
        assert result.payload.get("user_id") == "alice"

    def test_search_returns_result_with_data(self, db):
        vec = _vec(1.0)
        results = db.search(query="sci-fi", vectors=vec, top_k=5, filters={"user_id": "alice"})
        assert len(results) >= 1
        assert results[0].id == "doc1"
        assert 0.0 <= results[0].score <= 1.0
        # payload.data must be present — Mem0 drops results that do not have it
        assert results[0].payload.get("data") == "I love sci-fi"

    def test_search_returns_custom_metadata_used_in_filters(self, db):
        """select() can't wildcard — custom metadata is returned only when used as a filter key."""
        vec = _vec(7.0)
        db.insert([vec], [_payload("metadata test", "metauser", category="movies")], ["doc_meta"])

        results = db.search(
            query="metadata",
            vectors=vec,
            top_k=1,
            filters={"user_id": "metauser", "category": {"eq": "movies"}},
        )
        db.delete("doc_meta")

        assert len(results) >= 1
        assert results[0].payload.get("category") == "movies"

    def test_keyword_search(self, db):
        results = db.keyword_search(query="sci-fi", top_k=5, filters={"user_id": "alice"})
        assert results is not None
        assert len(results) >= 1
        assert results[0].id == "doc1"
        assert results[0].payload.get("data") == "I love sci-fi"

    def test_insert_multiple_and_list(self, db):
        vecs = [_vec(2.0), _vec(3.0)]
        payloads = [
            _payload("I enjoy hiking", "bob"),
            _payload("I like cooking", "bob"),
        ]
        db.insert(vecs, payloads, ["doc2", "doc3"])

        results = db.list(filters={"user_id": "bob"}, top_k=10)
        assert isinstance(results, list)
        ids = {r.id for r in results[0]}
        assert "doc2" in ids
        assert "doc3" in ids
        for r in results[0]:
            assert r.payload.get("data") is not None

    def test_update(self, db):
        new_vec = _vec(1.1)
        db.update("doc1", vector=new_vec, payload=_payload("I love hard sci-fi", "alice"))

        result = db.get("doc1")
        assert result is not None
        assert result.payload.get("data") == "I love hard sci-fi"

    def test_delete(self, db):
        db.delete("doc2")

        result = db.get("doc2")
        assert result is None

    def test_list_cols(self, db):
        cols = db.list_cols()
        assert COLLECTION in cols

    def test_score_is_similarity_not_distance(self, db):
        """Score must be higher=better (similarity), not distance."""
        vec = _vec(99.0)
        db.insert([vec], [_payload("similarity score test", "scoretest")], ["doc_score"])

        results = db.search(query="test", vectors=vec, top_k=1, filters={"user_id": "scoretest"})
        db.delete("doc_score")

        assert len(results) >= 1
        # Cosine similarity of a vector with itself = 1.0 → score should be very close to 1.0
        score = results[0].score
        assert score >= 0.95, f"Expected score near 1.0 (similarity), got {score}"

    def test_filter_eq_operator(self, db):
        results = db.search(
            query="sci-fi",
            vectors=_vec(1.0),
            top_k=5,
            filters={"user_id": {"eq": "alice"}},
        )
        assert len(results) >= 1
        for r in results:
            assert r.payload.get("user_id") == "alice"

    def test_filter_ne_operator(self, db):
        """ne should exclude alice; all results should belong to bob or other users."""
        results = db.search(
            query="hiking cooking",
            vectors=_vec(2.5),
            top_k=10,
            filters={"user_id": {"ne": "alice"}},
        )
        for r in results:
            assert r.payload.get("user_id") != "alice"

    def test_filter_in_operator(self, db):
        results = db.search(
            query="sci-fi hiking",
            vectors=_vec(1.5),
            top_k=10,
            filters={"user_id": {"in": ["alice", "bob"]}},
        )
        for r in results:
            assert r.payload.get("user_id") in ("alice", "bob")

    def test_reset(self, db):
        db.reset()
        # Collection should still exist after reset (recreated)
        info = db.col_info()
        assert info["name"] == COLLECTION


class TestUserIdIntegration:
    @pytest.fixture(scope="class", autouse=True)
    def cleanup_migrations(self):
        yield
        try:
            from topk_sdk import Client

            client = Client(
                api_key=os.environ["TOPK_API_KEY"],
                region=os.environ["TOPK_REGION"],
                **({"host": os.environ["TOPK_HOST"]} if os.environ.get("TOPK_HOST") else {}),
            )
            client.collections().delete("memory_migrations")
        except Exception:
            pass

    def test_get_user_id_persists_across_instances(self, db):
        id1 = db.get_user_id()
        assert isinstance(id1, str)
        assert len(id1) > 0

        store2 = TopK(collection_name=COLLECTION, embedding_model_dims=DIMS)
        assert store2.get_user_id() == id1

    def test_set_user_id_overwrites(self, db):
        db.set_user_id("custom-user-abc")

        store2 = TopK(collection_name=COLLECTION, embedding_model_dims=DIMS)
        assert store2.get_user_id() == "custom-user-abc"
