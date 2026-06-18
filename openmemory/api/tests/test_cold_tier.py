"""Tests for the cold_tier governance job (task_07 / ADR-003, ADR-005)."""

import json
import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.governance.cold_tier import run_cold_tier_job
from app.models import App, Base, Memory, MemoryState, Project, User

NOW = datetime(2026, 6, 18, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_categorize(monkeypatch):
    # O listener after_insert/after_update de Memory chama OpenAI (categorização);
    # neutraliza nos testes para isolar a lógica e evitar chamadas de rede.
    monkeypatch.setattr("app.models.categorize_memory", lambda *a, **k: None)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _seed(factory, *, project="p1", last_activity, n=3):
    db = factory()
    user = User(user_id="u1")
    app = App(owner=user, name="app1")
    db.add_all([user, app])
    db.flush()
    db.add(Project(name=project, last_activity_at=last_activity))
    for i in range(n):
        db.add(Memory(user_id=user.id, app_id=app.id, content=f"m{i}",
                      state=MemoryState.active, metadata_={"project": project}))
    db.commit()
    db.close()


class FakeVS:
    def __init__(self):
        self.deleted = []

    def delete(self, pid):
        self.deleted.append(pid)


def _active(factory, project="p1"):
    db = factory()
    try:
        return len([m for m in db.query(Memory).filter(Memory.state == MemoryState.active).all()
                    if (m.metadata_ or {}).get("project") == project])
    finally:
        db.close()


def test_active_project_not_archived(factory):
    _seed(factory, last_activity=NOW - timedelta(days=10))
    archive = {}
    n = run_cold_tier_job(project="p1", job_id="j", session_factory=factory,
                          vector_store_provider=FakeVS, archive_writer=lambda k, d: archive.update({k: d}),
                          clock=lambda: NOW)
    assert n == 0
    assert archive == {}
    assert _active(factory) == 3


def test_inactive_project_archived_and_removed(factory):
    _seed(factory, last_activity=NOW - timedelta(days=200))
    archive = {}
    vs = FakeVS()
    n = run_cold_tier_job(project="p1", job_id="j", session_factory=factory,
                          vector_store_provider=lambda: vs, archive_writer=lambda k, d: archive.update({k: d}),
                          clock=lambda: NOW)
    assert n == 3
    assert _active(factory) == 0           # memórias saíram do acervo quente
    assert len(vs.deleted) == 3            # removidas do Qdrant
    # export gravado antes da remoção, com as 3 memórias
    (key, data), = archive.items()
    assert key.startswith("cold/p1/")
    assert len(json.loads(data)) == 3


def test_export_failure_aborts_removal(factory):
    _seed(factory, last_activity=NOW - timedelta(days=200))

    def boom(key, data):
        raise RuntimeError("s3 down")

    with pytest.raises(RuntimeError):
        run_cold_tier_job(project="p1", job_id="j", session_factory=factory,
                          vector_store_provider=FakeVS, archive_writer=boom, clock=lambda: NOW)
    # Nada removido porque o export falhou antes da remoção.
    assert _active(factory) == 3


def test_no_activity_timestamp_is_noop(factory):
    _seed(factory, last_activity=None)
    n = run_cold_tier_job(project="p1", job_id="j", session_factory=factory,
                          vector_store_provider=FakeVS, archive_writer=lambda k, d: None, clock=lambda: NOW)
    assert n == 0
    assert _active(factory) == 3


def test_global_scope_is_noop(factory):
    _seed(factory, last_activity=NOW - timedelta(days=200))
    n = run_cold_tier_job(project=None, job_id="j", session_factory=factory,
                          vector_store_provider=FakeVS, archive_writer=lambda k, d: None, clock=lambda: NOW)
    assert n == 0
