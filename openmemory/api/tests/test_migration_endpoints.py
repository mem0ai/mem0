"""HTTP integration for the migration control endpoints (task_07).

Path-loads the admin router (avoiding heavy app.routers package deps) and drives
the start -> validate -> flip -> rollback cycle over HTTP with an injected
MigrationControl bound to SQLite + a fake count function.
"""

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.utils.migration_control import MigrationControl
from app.utils.partitioning import PartitionResolver

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "admin.py"
_spec = importlib.util.spec_from_file_location("admin_under_test_07", _PATH)
_admin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admin)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    counts = {"blue": 100, "green": 100}
    resolver = PartitionResolver(session_factory=factory, default_collection="blue")
    control = MigrationControl(
        session_factory=factory, count_fn=lambda c: counts.get(c, 0), resolver=resolver
    )

    app = FastAPI()
    app.include_router(_admin.router)
    app.dependency_overrides[_admin._control] = lambda: control

    yield TestClient(app), resolver
    engine.dispose()


def test_full_cycle_start_flip_rollback(client):
    tc, resolver = client

    r = tc.post("/admin/migration/start",
                json={"source_collection": "blue", "target_collection": "green"})
    assert r.status_code == 200
    assert r.json()["active_collection"] == "blue"
    assert r.json()["dual_write_enabled"] is True

    r = tc.post("/admin/migration/validate")
    assert r.status_code == 200 and r.json()["ok"] is True

    r = tc.post("/admin/migration/flip")
    assert r.status_code == 200
    assert r.json()["active_collection"] == "green"
    assert resolver.active_collection() == "green"

    r = tc.post("/admin/migration/rollback")
    assert r.status_code == 200
    assert r.json()["active_collection"] == "blue"
    assert resolver.active_collection() == "blue"


def test_flip_is_idempotent(client):
    tc, _ = client
    tc.post("/admin/migration/start",
            json={"source_collection": "blue", "target_collection": "green"})
    first = tc.post("/admin/migration/flip")
    second = tc.post("/admin/migration/flip")
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["active_collection"] == "green"


def test_start_rejects_same_collections(client):
    tc, _ = client
    r = tc.post("/admin/migration/start",
                json={"source_collection": "x", "target_collection": "x"})
    assert r.status_code == 400
