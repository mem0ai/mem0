import pytest

from mem0.vector_stores.faiss import FAISS


@pytest.mark.parametrize("vector", [[1.0], ["invalid", 0.0]])
def test_invalid_update_preserves_persisted_memory(tmp_path, vector):
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["original"], payloads=[{"data": "original"}])

    with pytest.raises((ValueError, AssertionError)):
        store.update("original", vector=vector, payload={"data": "replacement"})

    assert store.get("original").payload == {"data": "original"}
    assert store.col_info()["count"] == 1
    reloaded = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    assert reloaded.get("original").payload == {"data": "original"}
    assert [r.id for r in reloaded.search("", [1.0, 0.0])] == ["original"]


def test_valid_vector_and_payload_update_survives_reload(tmp_path):
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["original"], payloads=[{"data": "original"}])
    store.update("original", vector=[0.0, 1.0], payload={"data": "replacement"})
    reloaded = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    assert reloaded.get("original").payload == {"data": "replacement"}
    assert reloaded.col_info()["count"] == 1
    assert reloaded.search("", [0.0, 1.0])[0].score == pytest.approx(1.0)
