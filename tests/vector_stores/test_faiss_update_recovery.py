import os
import subprocess
import sys
from unittest.mock import patch

import faiss
import pytest

from mem0.vector_stores.faiss import FAISS


def populated(path):
    store = FAISS("memories", path=str(path), embedding_model_dims=2)
    store.insert(
        [[1.0, 0.0], [0.0, 1.0]], ids=["original", "other"], payloads=[{"data": "original"}, {"data": "other"}]
    )
    return store


def assert_original(store):
    assert store.get("original").payload == {"data": "original"}
    assert store.get("other").payload == {"data": "other"}
    assert store.col_info()["count"] == 2
    assert store.search("", [1.0, 0.0])[0].id == "original"


def test_loaded_dimension_warning_and_rejected_update(tmp_path, caplog):
    populated(tmp_path)
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=1)
    assert "dimension" in caplog.text.lower()
    with pytest.raises(ValueError):
        store.update("original", [1.0], {"data": "replacement"})
    assert_original(store)
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


def test_native_insert_failure_preserves_memory_and_disk(tmp_path):
    store = populated(tmp_path)
    with patch.object(faiss.IndexFlatL2, "add", side_effect=RuntimeError("native add failed")):
        with pytest.raises(RuntimeError, match="native add failed"):
            store.update("original", [0.5, 0.5], {"data": "replacement"})
    assert_original(store)
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


@pytest.mark.parametrize("failure", ["serialization", "index_write", "json_replace"])
def test_save_failure_preserves_memory_and_disk(tmp_path, monkeypatch, failure):
    store = populated(tmp_path)
    payload = {"data": "replacement"}
    if failure == "serialization":
        payload["bad"] = object()
        error = TypeError
    elif failure == "index_write":
        monkeypatch.setattr(faiss, "write_index", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
        error = OSError
    else:
        replace = os.replace
        failed = False

        def fail_once(src, dst):
            nonlocal failed
            if str(dst).endswith("memories.json") and not failed:
                failed = True
                raise OSError("replace failed")
            return replace(src, dst)

        monkeypatch.setattr(os, "replace", fail_once)
        error = OSError
    with pytest.raises(error):
        store.update("original", [0.5, 0.5], payload)
    assert_original(store)
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


@pytest.mark.parametrize("boundary", ["faiss", "json", "commit"])
def test_process_exit_during_save_recovers_consistent_pair(tmp_path, boundary):
    populated(tmp_path)
    script = """
import os, sys
from mem0.vector_stores.faiss import FAISS
store = FAISS('memories', path=sys.argv[1], embedding_model_dims=2)
replace, unlink = os.replace, os.unlink
boundary = sys.argv[2]
def crash_replace(src, dst):
    replace(src, dst)
    if boundary in ('faiss', 'json') and str(dst).endswith('memories.' + boundary):
        os._exit(73)
def crash_unlink(path, *args, **kwargs):
    unlink(path, *args, **kwargs)
    if boundary == 'commit' and str(path).endswith('.rollback'):
        os._exit(73)
os.replace, os.unlink = crash_replace, crash_unlink
store.update('original', [0.5, 0.5], {'data': 'replacement'})
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), boundary],
        env={**os.environ, "MEM0_TELEMETRY": "False"},
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 73, result.stderr.decode()
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    if boundary == "commit":
        assert store.get("original").payload == {"data": "replacement"}
        assert store.search("", [0.5, 0.5])[0].score == pytest.approx(1.0)
        assert store.get("other").payload == {"data": "other"}
    else:
        assert_original(store)
    assert store.col_info()["count"] == 2
    assert not (tmp_path / "memories.rollback").exists()


def test_failed_rollback_can_be_retried_on_reopen(tmp_path, monkeypatch):
    store = populated(tmp_path)
    replace = os.replace

    def fail_json(src, dst):
        if str(dst).endswith("memories.json"):
            raise OSError("disk unavailable")
        return replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_json)
    with pytest.raises(OSError):
        store.update("original", [0.5, 0.5], {"data": "replacement"})
    assert_original(store)
    assert (tmp_path / "memories.rollback").exists()
    with pytest.raises(OSError):
        FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    with pytest.raises(RuntimeError, match="reopen"):
        store.update("original", [0.5, 0.5])
    monkeypatch.setattr(os, "replace", replace)
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


def test_payload_only_failure_leaves_memory_unchanged(tmp_path):
    store = populated(tmp_path)
    with pytest.raises(TypeError):
        store.update("original", payload={"data": object()})
    assert_original(store)
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


@pytest.mark.parametrize("strategy", ["euclidean", "cosine", "inner_product"])
def test_successful_update_preserves_neighbours_and_search(tmp_path, strategy):
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2, distance_strategy=strategy)
    store.insert(
        [[1.0, 0.0], [0.0, 1.0]], ids=["original", "other"], payloads=[{"data": "original"}, {"data": "other"}]
    )
    assert store.update("original", [4.0, 4.0], {"data": "replacement"}) is True
    loaded = FAISS("memories", path=str(tmp_path), embedding_model_dims=2, distance_strategy=strategy)
    assert loaded.get("other").payload == {"data": "other"}
    assert loaded.search("", [4.0, 4.0])[0].id == "original"
    assert loaded.col_info()["count"] == 2
    if strategy == "cosine":
        assert loaded.search("", [4.0, 4.0])[0].score == pytest.approx(1.0)


def test_process_exit_during_recovery_can_be_retried(tmp_path):
    populated(tmp_path)
    script = """
import os, sys
from mem0.vector_stores.faiss import FAISS
replace = os.replace
def crash(src, dst):
    replace(src, dst)
    if str(dst).endswith('memories.faiss'):
        os._exit(73)
if sys.argv[2] == 'save':
    store = FAISS('memories', path=sys.argv[1], embedding_model_dims=2)
    os.replace = crash
    store.update('original', [0.5, 0.5], {'data': 'replacement'})
else:
    os.replace = crash
    FAISS('memories', path=sys.argv[1], embedding_model_dims=2)
"""
    for stage in ["save", "recover"]:
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), stage],
            env={**os.environ, "MEM0_TELEMETRY": "False"},
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 73, result.stderr.decode()
        assert (tmp_path / "memories.rollback").exists()
    assert_original(FAISS("memories", path=str(tmp_path), embedding_model_dims=2))


def test_corrupt_metadata_does_not_open_an_empty_store(tmp_path):
    populated(tmp_path)
    (tmp_path / "memories.json").write_text("{broken")
    before = (tmp_path / "memories.faiss").read_bytes()
    with pytest.raises(ValueError, match="Failed to load FAISS collection"):
        FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    assert (tmp_path / "memories.faiss").read_bytes() == before
    assert (tmp_path / "memories.json").read_text() == "{broken"
