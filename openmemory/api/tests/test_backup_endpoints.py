"""Tests for the /admin/backup/* endpoints (task_03 / ADR-003)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.admin import _backup_service, router


class FakeBackup:
    def __init__(self, exists=True):
        self._exists = exists
        self.ran = False
        self.restored = None

    def run_backup(self):
        self.ran = True

    def status(self):
        return {"last_backup": "backups/2026-06-18/postgres/dump.sql.gz", "objects": 3, "rpo_age_seconds": 0}

    def exists(self, key_prefix):
        return self._exists

    def restore(self, key_prefix):
        self.restored = key_prefix


@pytest.fixture
def app_and_fake():
    fake = FakeBackup()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_backup_service] = lambda: fake
    return app, fake


def test_backup_run_returns_202_and_triggers(app_and_fake):
    app, fake = app_and_fake
    with TestClient(app) as client:
        resp = client.post("/admin/backup/run")
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert fake.ran is True


def test_backup_status_returns_rpo(app_and_fake):
    app, fake = app_and_fake
    with TestClient(app) as client:
        resp = client.get("/admin/backup/status")
    assert resp.status_code == 200
    assert resp.json()["objects"] == 3
    assert resp.json()["rpo_age_seconds"] == 0


def test_restore_existing_prefix_accepted(app_and_fake):
    app, fake = app_and_fake
    with TestClient(app) as client:
        resp = client.post("/admin/backup/restore", json={"key_prefix": "backups/2026-06-18"})
    assert resp.status_code == 202
    assert fake.restored == "backups/2026-06-18"


def test_restore_missing_prefix_returns_404():
    fake = FakeBackup(exists=False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_backup_service] = lambda: fake
    with TestClient(app) as client:
        resp = client.post("/admin/backup/restore", json={"key_prefix": "backups/nope"})
    assert resp.status_code == 404
    assert fake.restored is None
