"""Tests for the enforce_quota governance job (task_06 / ADR-005)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.governance.quota import run_enforce_quota_job
from app.models import App, Base, Memory, MemoryState, User
from app.utils.governance_policy import save_global_policy
from app.utils.quarantine import QuarantineEngine


@pytest.fixture(autouse=True)
def _no_categorize(monkeypatch):
    # Evita a categorização via OpenAI disparada pelo listener de Memory.
    monkeypatch.setattr("app.models.categorize_memory", lambda *a, **k: None)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _seed(factory, n, *, project="p1", pinned_idx=()):
    db = factory()
    user = User(user_id="u1")
    app = App(owner=user, name="app1")
    db.add_all([user, app])
    db.flush()
    for i in range(n):
        meta = {"project": project}
        if i in pinned_idx:
            meta["pinned"] = True
        db.add(Memory(user_id=user.id, app_id=app.id, content=f"m{i}", state=MemoryState.active, metadata_=meta))
    db.commit()
    db.close()


def _active_count(factory, project="p1"):
    db = factory()
    try:
        return len(
            [
                m
                for m in db.query(Memory).filter(Memory.state == MemoryState.active).all()
                if (m.metadata_ or {}).get("project") == project
            ]
        )
    finally:
        db.close()


def _engine(factory):
    return QuarantineEngine(session_factory=factory, vector_store_provider=lambda: None)


def _set_policy(factory, **fields):
    db = factory()
    try:
        save_global_policy(db, fields)
    finally:
        db.close()


def _run(factory, project="p1"):
    return run_enforce_quota_job(
        project=project, job_id="j", session_factory=factory, quarantine_engine=_engine(factory)
    )


def test_no_teto_is_noop(factory):
    _seed(factory, 5)
    _set_policy(factory, max_memories=None)
    assert _run(factory) == 0
    assert _active_count(factory) == 5


def test_alert_mode_does_not_remove(factory):
    _seed(factory, 5)
    _set_policy(factory, max_memories=2, max_memories_action="alert")
    assert _run(factory) == 0
    assert _active_count(factory) == 5


def test_enforce_reduces_to_teto(factory):
    _seed(factory, 5)
    _set_policy(factory, max_memories=2, max_memories_action="enforce")
    assert _run(factory) == 3
    assert _active_count(factory) == 2


def test_enforce_skips_pinned(factory):
    # 4 memories, 2 pinned; teto 1 → só dá para quarentenar as 2 não-pinned.
    _seed(factory, 4, pinned_idx=(0, 1))
    _set_policy(factory, max_memories=1, max_memories_action="enforce")
    assert _run(factory) == 2  # apenas as 2 não-pinned
    assert _active_count(factory) == 2  # 2 pinned permanecem (protegidas)


def test_under_teto_is_noop(factory):
    _seed(factory, 2)
    _set_policy(factory, max_memories=5, max_memories_action="enforce")
    assert _run(factory) == 0
    assert _active_count(factory) == 2


def test_global_scope_is_noop(factory):
    _seed(factory, 5)
    _set_policy(factory, max_memories=2, max_memories_action="enforce")
    assert _run(factory, project=None) == 0
