import json
import os
import subprocess
import sys
from unittest.mock import Mock, patch

import faiss
import pytest

from mem0 import Memory
from mem0.vector_stores.faiss import FAISS


def test_public_add_retry_does_not_duplicate_vectors(tmp_path):
    embedder = Mock()
    embedder.embed.return_value = [1.0, 0.0]
    embedder.embed_batch.side_effect = lambda texts, *a: [[1.0, 0.0] for _ in texts]
    llm = Mock()
    llm.generate_response.return_value = json.dumps({"memory": [{"text": "I prefer tea."}]})
    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=llm),
    ):
        memory = Memory.from_config(
            {
                "vector_store": {
                    "provider": "faiss",
                    "config": {
                        "collection_name": "memories",
                        "path": str(tmp_path),
                        "embedding_model_dims": 2,
                    },
                },
                "history_db_path": str(tmp_path / "history.db"),
            }
        )
    write = faiss.write_index
    failed = False

    def fail_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("temporary write failure")
        return write(*args)

    with patch("faiss.write_index", side_effect=fail_once):
        result = memory.add("I prefer tea.", user_id="review-user")
    memory_id = result["results"][0]["id"]
    assert len(result["results"]) == 1
    assert memory.vector_store.index.ntotal == 1
    loaded = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    assert [row.id for row in loaded.search("", [1.0, 0.0])] == [memory_id]
    assert [row["event"] for row in memory.history(memory_id)] == ["ADD"]
    memory.delete(memory_id)
    assert memory.vector_store.index.ntotal == 0
    assert memory.vector_store.index_to_id == {}
    assert FAISS("memories", path=str(tmp_path), embedding_model_dims=2).index.ntotal == 0


@pytest.mark.parametrize("operation", ["insert", "delete"])
def test_failed_write_does_not_leak_into_next_save(tmp_path, operation):
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["original"], payloads=[{"data": "original"}])
    with patch("faiss.write_index", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            if operation == "insert":
                store.insert([[0.0, 1.0]], ids=["rejected"], payloads=[{}])
            else:
                store.delete("original")
    assert store.get("original").payload == {"data": "original"}
    assert store.get("rejected") is None
    assert store.index.ntotal == 1
    store.update("original", payload={"data": "next successful write"})
    loaded = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    assert loaded.index.ntotal == 1
    assert loaded.get("rejected") is None
    assert loaded.get("original").payload["data"] == "next successful write"


@pytest.mark.parametrize("boundary", ["index", "journal"])
def test_reopen_cleans_unpublished_save_files(tmp_path, boundary):
    store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
    store.insert([[1.0, 0.0]], ids=["original"], payloads=[{"data": "original"}])
    other = tmp_path / ".memories-other-abcdefgh"
    other.write_bytes(b"other collection temporary")
    script = """
import os, sys, faiss
from mem0.vector_stores.faiss import FAISS
store = FAISS('memories', path=sys.argv[1], embedding_model_dims=2)
write, replace = faiss.write_index, os.replace
def crash_write(index, path):
    write(index, path)
    if sys.argv[2] == 'index': os._exit(73)
def crash_replace(src, dst):
    if str(dst).endswith('.rollback'): os._exit(73)
    replace(src, dst)
faiss.write_index, os.replace = crash_write, crash_replace
store.update('original', [0., 1.], {'data': 'replacement'})
"""
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), boundary],
            capture_output=True,
            timeout=30,
            env={**os.environ, "MEM0_TELEMETRY": "False"},
        )
        assert result.returncode == 73, result.stderr.decode()
        store = FAISS("memories", path=str(tmp_path), embedding_model_dims=2)
        assert store.get("original").payload == {"data": "original"}
        assert list(tmp_path.glob(".memories-*")) == [other]
    store.delete_col()
    assert list(tmp_path.iterdir()) == [other]
