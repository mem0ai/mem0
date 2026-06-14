import tempfile

import numpy as np
import pytest

quantal = pytest.importorskip("quantal", reason="quantaldb not installed (pip install quantaldb)")

from mem0.vector_stores.quantal import Quantal  # noqa: E402

DIMS = 256


def _vec(seed: int) -> list:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIMS).astype(np.float32)
    return (v / np.linalg.norm(v)).tolist()


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = Quantal(collection_name="test", path=temp_dir, embedding_model_dims=DIMS)
        yield store
        store.delete_col()


def test_insert_and_search(store):
    vectors = [_vec(1), _vec(2), _vec(3)]
    payloads = [{"user_id": "alice"}, {"user_id": "bob"}, {"user_id": "alice"}]
    ids = ["id1", "id2", "id3"]
    store.insert(vectors, payloads, ids)

    results = store.search("query", [vectors[1]], top_k=2)
    assert results[0].id == "id2"
    assert results[0].payload == {"user_id": "bob"}
    assert results[0].score == pytest.approx(1.0, abs=0.05)


def test_search_with_filters(store):
    vectors = [_vec(1), _vec(2), _vec(3)]
    payloads = [{"user_id": "alice"}, {"user_id": "bob"}, {"user_id": "alice"}]
    store.insert(vectors, payloads, ["id1", "id2", "id3"])

    results = store.search("query", [vectors[1]], top_k=3, filters={"user_id": "alice"})
    assert {r.id for r in results} == {"id1", "id3"}

    assert store.search("query", [vectors[0]], top_k=3, filters={"user_id": "carol"}) == []


def test_search_empty_collection(store):
    assert store.search("query", [_vec(1)], top_k=5) == []


def test_delete(store):
    store.insert([_vec(1), _vec(2)], [{"a": 1}, {"a": 2}], ["id1", "id2"])
    store.delete("id1")

    assert store.get("id1") is None
    results = store.search("query", [_vec(1)], top_k=2)
    assert [r.id for r in results] == ["id2"]


def test_update_payload(store):
    store.insert([_vec(1)], [{"a": 1}], ["id1"])
    store.update("id1", payload={"a": 2})
    assert store.get("id1").payload == {"a": 2}


def test_update_vector(store):
    store.insert([_vec(1), _vec(2)], [{"a": 1}, {"a": 2}], ["id1", "id2"])
    store.update("id1", vector=_vec(9))

    results = store.search("query", [_vec(9)], top_k=1)
    assert results[0].id == "id1"
    assert results[0].payload == {"a": 1}


def test_update_missing_raises(store):
    with pytest.raises(ValueError):
        store.update("missing", payload={"a": 1})


def test_get(store):
    store.insert([_vec(1)], [{"a": 1}], ["id1"])
    result = store.get("id1")
    assert result.id == "id1"
    assert result.payload == {"a": 1}
    assert store.get("missing") is None


def test_list(store):
    store.insert([_vec(1), _vec(2)], [{"user_id": "alice"}, {"user_id": "bob"}], ["id1", "id2"])

    [results] = store.list()
    assert {r.id for r in results} == {"id1", "id2"}

    [results] = store.list(filters={"user_id": "alice"})
    assert [r.id for r in results] == ["id1"]


def test_list_cols_and_col_info(store):
    store.insert([_vec(1)], [{"a": 1}], ["id1"])
    assert "test" in store.list_cols()

    info = store.col_info()
    assert info["name"] == "test"
    assert info["count"] == 1
    assert info["dimension"] == DIMS
    assert info["distance"] == "cosine"
    assert info["memory_bytes"] > 0


def test_persistence_roundtrip():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = Quantal(collection_name="test", path=temp_dir, embedding_model_dims=DIMS)
        store.insert([_vec(1), _vec(2)], [{"a": 1}, {"a": 2}], ["id1", "id2"])
        store.delete("id2")
        del store

        reloaded = Quantal(collection_name="test", path=temp_dir, embedding_model_dims=DIMS)
        assert reloaded.get("id1").payload == {"a": 1}
        assert reloaded.get("id2") is None
        results = reloaded.search("query", [_vec(1)], top_k=1)
        assert results[0].id == "id1"

        # New inserts after a reload must not collide with prior internal ids.
        reloaded.insert([_vec(3)], [{"a": 3}], ["id3"])
        assert reloaded.get("id3").payload == {"a": 3}
        reloaded.delete_col()


def test_reset(store):
    store.insert([_vec(1)], [{"a": 1}], ["id1"])
    store.reset()
    assert store.get("id1") is None
    assert store.col_info()["count"] == 0
