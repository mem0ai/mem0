"""Tests for conditional dual-write to the migration target (task_05 / ADR-003).

Worker-level: the just-written delta is mirrored to the target only when
``dual_write_enabled``; replication failures are counted and swallowed (the job
is never failed by a mirror error). Vector-store level: ``replicate_to`` copies
points by id (idempotent upsert) and ``delete_from`` removes them.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import uuid
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client import QdrantClient

from app.workers.write_worker import WriteWorker
from app.utils.metrics import DUAL_WRITE_ERRORS
from mem0.vector_stores.qdrant import Qdrant


# --------------------------------------------------------------------------- #
# Worker-level dual-write
# --------------------------------------------------------------------------- #
def _worker():
    return WriteWorker(queue=MagicMock(), client_provider=lambda: None)


def _client_with_vs():
    client = MagicMock()
    client.vector_store = MagicMock(spec=["replicate_to", "delete_from", "collection_name"])
    return client


def test_dual_write_disabled_is_noop():
    worker = _worker()
    client = _client_with_vs()
    with patch("app.workers.write_worker.partition_resolver") as resolver:
        resolver.dual_write_target.return_value = None
        worker._maybe_dual_write(client, {"results": [{"id": "1", "event": "ADD"}]})
    client.vector_store.replicate_to.assert_not_called()
    client.vector_store.delete_from.assert_not_called()


def test_dual_write_replicates_adds_and_deletes():
    worker = _worker()
    client = _client_with_vs()
    result = {
        "results": [
            {"id": "a1", "event": "ADD"},
            {"id": "a2", "event": "UPDATE"},
            {"id": "d1", "event": "DELETE"},
        ]
    }
    with patch("app.workers.write_worker.partition_resolver") as resolver:
        resolver.dual_write_target.return_value = "green"
        worker._maybe_dual_write(client, result)

    client.vector_store.replicate_to.assert_called_once_with(["a1", "a2"], "green")
    client.vector_store.delete_from.assert_called_once_with(["d1"], "green")


def test_dual_write_failure_is_counted_and_swallowed():
    worker = _worker()
    client = _client_with_vs()
    client.vector_store.replicate_to.side_effect = RuntimeError("target down")

    before = DUAL_WRITE_ERRORS._value.get()
    with patch("app.workers.write_worker.partition_resolver") as resolver:
        resolver.dual_write_target.return_value = "green"
        # Must NOT raise — the active write already succeeded.
        worker._maybe_dual_write(client, {"results": [{"id": "a1", "event": "ADD"}]})
    after = DUAL_WRITE_ERRORS._value.get()

    assert after == before + 1


# --------------------------------------------------------------------------- #
# Vector-store primitives
# --------------------------------------------------------------------------- #
class TestQdrantReplication:
    def _qdrant(self):
        client_mock = MagicMock(spec=QdrantClient)
        client_mock.get_collections.return_value = MagicMock(collections=[])
        return Qdrant(collection_name="blue", embedding_model_dims=128, client=client_mock), client_mock

    def test_replicate_to_preserves_ids(self):
        qdrant, client_mock = self._qdrant()
        rec = MagicMock(id="p1", vector={"": [0.1, 0.2]}, payload={"data": "x"})
        client_mock.retrieve.return_value = [rec]

        qdrant.replicate_to(["p1"], "green")

        client_mock.retrieve.assert_called_once_with(
            collection_name="blue", ids=["p1"], with_payload=True, with_vectors=True
        )
        upsert_kwargs = client_mock.upsert.call_args.kwargs
        assert upsert_kwargs["collection_name"] == "green"
        assert upsert_kwargs["points"][0].id == "p1"

    def test_replicate_to_empty_is_noop(self):
        qdrant, client_mock = self._qdrant()
        qdrant.replicate_to([], "green")
        client_mock.retrieve.assert_not_called()
        client_mock.upsert.assert_not_called()

    def test_delete_from_target(self):
        qdrant, client_mock = self._qdrant()
        qdrant.delete_from(["p1", "p2"], "green")
        kwargs = client_mock.delete.call_args.kwargs
        assert kwargs["collection_name"] == "green"

    def test_delete_from_empty_is_noop(self):
        qdrant, client_mock = self._qdrant()
        qdrant.delete_from([], "green")
        client_mock.delete.assert_not_called()
