"""Tests for operational visibility endpoints (task_09).

Exercises GET /admin/projects/sizes against in-memory SQLite via a FastAPI
dependency override. Imports the admin router directly to avoid the heavy
app.routers package __init__.
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

from app.database import get_db
from app.models import Base, PartitionTier, Project
from app.utils.metrics import PROJECT_SIZE_OVER_THRESHOLD

# Path-load the router module directly: importing it via the app.routers package
# would pull heavy deps (fastapi_pagination, an import-time OpenAI client) not
# installed outside Docker. admin.py's own imports are light (database/models/metrics).
_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "admin.py"
_spec = importlib.util.spec_from_file_location("admin_under_test", _PATH)
_admin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admin)
router = _admin.router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PROJECT_PROMOTION_THRESHOLD", "1000")
    # StaticPool + a single shared connection so the sync endpoint (run in a
    # worker thread by TestClient) sees the same in-memory database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = factory()
    db.add(Project(name="small", memory_count=10))
    db.add(Project(name="big", memory_count=5000,
                   partition_tier=PartitionTier.dedicated, shard_key="big"))
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    engine.dispose()


def test_sizes_lists_projects_with_tier_and_flag(client):
    resp = client.get("/admin/projects/sizes")
    assert resp.status_code == 200
    body = resp.json()

    assert body["threshold"] == 1000
    by_name = {p["name"]: p for p in body["projects"]}

    assert by_name["small"]["over_threshold"] is False
    assert by_name["small"]["partition_tier"] == "shared"
    assert by_name["small"]["shard_key"] is None

    assert by_name["big"]["over_threshold"] is True
    assert by_name["big"]["partition_tier"] == "dedicated"
    assert by_name["big"]["shard_key"] == "big"


def test_over_threshold_count_and_metric(client):
    resp = client.get("/admin/projects/sizes")
    body = resp.json()
    assert body["over_threshold_count"] == 1
    assert PROJECT_SIZE_OVER_THRESHOLD._value.get() == 1
