"""Tests for giant-project promotion to a dedicated shard key (task_08 / ADR-002).

Drives PromotionService against a mocked Qdrant vector store and SQLite, plus an
HTTP test of the non-blocking /promote endpoint. No live Qdrant required.
"""

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, PartitionTier, Project
from app.utils.partitioning import PartitionResolver
from app.utils.promotion import PromotionService


def _rec(point_id):
    return MagicMock(id=point_id, vector={"": [0.1, 0.2]}, payload={"project": "big", "data": point_id})


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'promo.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    f = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = f()
    db.add(Project(name="big", memory_count=5000))
    db.commit()
    db.close()
    yield f
    engine.dispose()


def _vs():
    vs = MagicMock()
    vs.collection_name = "openmemory"
    vs._create_filter.return_value = {"project": "big"}  # opaque to the mock
    return vs


def _service(factory, vs, resolver=None):
    return PromotionService(
        session_factory=factory,
        vector_store_provider=lambda: vs,
        resolver=resolver or PartitionResolver(session_factory=factory, default_collection="openmemory"),
    )


def test_promote_creates_shard_key_and_moves_points(factory):
    vs = _vs()
    vs.client.scroll.side_effect = [([_rec("p1"), _rec("p2")], None)]
    resolver = PartitionResolver(session_factory=factory, default_collection="openmemory")

    result = _service(factory, vs, resolver).promote("big")

    vs.create_shard_key.assert_called_once_with("big")
    # points re-upserted into the same collection with the dedicated shard key.
    ukwargs = vs.client.upsert.call_args.kwargs
    assert ukwargs["collection_name"] == "openmemory"
    assert ukwargs["shard_key_selector"] == "big"
    assert [p.id for p in ukwargs["points"]] == ["p1", "p2"]
    assert result["moved"] == 2

    # Project marked dedicated; resolver now routes "big" to its shard key.
    assert resolver.route_for("big").shard_key == "big"


def test_promote_marks_project_dedicated(factory):
    vs = _vs()
    vs.client.scroll.side_effect = [([], None)]
    _service(factory, vs).promote("big")

    db = factory()
    try:
        proj = db.query(Project).filter_by(name="big").one()
        assert proj.partition_tier == PartitionTier.dedicated
        assert proj.shard_key == "big"
    finally:
        db.close()


def test_promote_is_idempotent_when_shard_key_exists(factory):
    vs = _vs()
    vs.create_shard_key.side_effect = RuntimeError("shard key already exists")
    vs.client.scroll.side_effect = [([_rec("dup")], None)]

    # Must not raise; still moves points and marks dedicated.
    result = _service(factory, vs).promote("big")
    assert result["moved"] == 1


def test_promote_paginates_until_drained(factory):
    vs = _vs()
    vs.client.scroll.side_effect = [
        ([_rec("p1")], "o1"),
        ([_rec("p2")], None),
    ]
    _service(factory, vs).promote("big")
    assert vs.client.scroll.call_count == 2
    assert vs.client.upsert.call_count == 2


# --------------------------------------------------------------------------- #
# Endpoint
# --------------------------------------------------------------------------- #
_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "admin.py"
_spec = importlib.util.spec_from_file_location("admin_under_test_08", _PATH)
_admin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admin)


def test_promote_endpoint_accepts_and_schedules():
    service = MagicMock()
    app = FastAPI()
    app.include_router(_admin.router)
    app.dependency_overrides[_admin._promotion] = lambda: service

    resp = TestClient(app).post("/admin/projects/big/promote")

    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted", "project": "big", "shard_key": "big"}
    # Work runs via BackgroundTasks (after the response), not inline in the handler.
    service.promote.assert_called_once_with("big")
