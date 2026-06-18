"""Tests for the blue-green migration worker (task_06 / ADR-003).

Drives ``copy_once``/``run_copy`` against a mocked Qdrant client and SQLite-backed
``migration_state``. Verifies provisioning-before-load, id-preserving copy,
checkpoint persistence, idempotent resume, and status transitions.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, MigrationState, MigrationStatus
from app.workers.migration_worker import MigrationWorker


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    f = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = f()
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="green",
            active_collection="blue",
            status=MigrationStatus.planned,
        )
    )
    db.commit()
    db.close()
    yield f
    engine.dispose()


def _rec(point_id):
    return MagicMock(id=point_id, vector={"": [0.1, 0.2]}, payload={"data": point_id})


def _status(factory):
    db = factory()
    try:
        return db.query(MigrationState).first().status
    finally:
        db.close()


def _cursor(factory):
    db = factory()
    try:
        return db.query(MigrationState).first().scroll_cursor
    finally:
        db.close()


def test_provision_target_called_with_target(factory):
    provisioner = MagicMock()
    worker = MigrationWorker(session_factory=factory, client=MagicMock(), provisioner=provisioner)
    worker.provision_target()
    provisioner.assert_called_once_with("green")


def test_copy_once_preserves_ids_and_checkpoints(factory):
    client = MagicMock()
    client.scroll.return_value = ([_rec("p1"), _rec("p2")], "offset-2")
    worker = MigrationWorker(session_factory=factory, client=client, provisioner=MagicMock())

    more = worker.copy_once()

    assert more is True
    # scroll reads from source, with vectors+payload.
    skwargs = client.scroll.call_args.kwargs
    assert skwargs["collection_name"] == "blue"
    assert skwargs["with_vectors"] is True
    # upsert writes to target preserving ids.
    ukwargs = client.upsert.call_args.kwargs
    assert ukwargs["collection_name"] == "green"
    assert [p.id for p in ukwargs["points"]] == ["p1", "p2"]
    # checkpoint persisted; status moved to copying.
    assert json.loads(_cursor(factory)) == "offset-2"
    assert _status(factory) == MigrationStatus.copying


def test_copy_once_final_batch_sets_validating(factory):
    client = MagicMock()
    client.scroll.return_value = ([_rec("p3")], None)  # None => no more pages
    worker = MigrationWorker(session_factory=factory, client=client, provisioner=MagicMock())

    more = worker.copy_once()

    assert more is False
    assert _status(factory) == MigrationStatus.validating


def test_copy_resumes_from_checkpoint(factory):
    # Seed an existing checkpoint.
    db = factory()
    db.query(MigrationState).first()
    db.query(MigrationState).update({"scroll_cursor": json.dumps("offset-1")})
    db.commit()
    db.close()

    client = MagicMock()
    client.scroll.return_value = ([_rec("p9")], None)
    worker = MigrationWorker(session_factory=factory, client=client, provisioner=MagicMock())
    worker.copy_once()

    assert client.scroll.call_args.kwargs["offset"] == "offset-1"


def test_run_copy_loops_until_drained_and_provisions_once(factory):
    client = MagicMock()
    # Two pages then exhaustion.
    client.scroll.side_effect = [
        ([_rec("p1")], "o1"),
        ([_rec("p2")], "o2"),
        ([_rec("p3")], None),
    ]
    provisioner = MagicMock()
    worker = MigrationWorker(session_factory=factory, client=client, provisioner=provisioner)

    worker.run_copy()

    provisioner.assert_called_once_with("green")
    assert client.scroll.call_count == 3
    assert client.upsert.call_count == 3
    assert _status(factory) == MigrationStatus.validating


def test_idempotent_reupsert_same_ids(factory):
    client = MagicMock()
    client.scroll.return_value = ([_rec("dup")], "o1")
    worker = MigrationWorker(session_factory=factory, client=client, provisioner=MagicMock())

    worker.copy_once()
    worker.copy_once()

    # Both passes upsert the same id (idempotent at the Qdrant layer).
    for call in client.upsert.call_args_list:
        assert [p.id for p in call.kwargs["points"]] == ["dup"]
