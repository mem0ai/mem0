"""Tests for quarantine engine (task_04)."""

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Memory,
    MemoryState,
    MemoryStatusHistory,
    User,
    App,
)
from app.utils.quarantine import QuarantineEngine


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'q.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    return factory


def _memory(db, *, pinned=False, state=MemoryState.active, suffix=""):
    user = User(user_id=f"u{suffix}")
    app = App(owner=user, name=f"a{suffix}")
    db.add_all([user, app])
    db.flush()
    mem = Memory(
        user_id=user.id,
        app_id=app.id,
        content="hello",
        state=state,
        metadata_={"pinned": True} if pinned else {},
    )
    db.add(mem)
    db.commit()
    return mem


def test_quarantine_skips_pinned(session_factory):
    db = session_factory()
    mem = _memory(db, pinned=True)
    engine = QuarantineEngine(session_factory=session_factory, vector_store_provider=lambda: None)
    assert engine.quarantine(mem.id, reason="dedup", job_id="j1") is False
    db2 = session_factory()
    loaded = db2.query(Memory).filter_by(id=mem.id).one()
    assert loaded.state == MemoryState.active
    db2.close()
    db.close()


def test_quarantine_and_revert(session_factory):
    db = session_factory()
    mem = _memory(db)
    engine = QuarantineEngine(session_factory=session_factory, vector_store_provider=lambda: None)
    assert engine.quarantine(mem.id, reason="dedup", job_id="j1") is True
    db2 = session_factory()
    loaded = db2.query(Memory).filter_by(id=mem.id).one()
    assert loaded.state == MemoryState.quarantined
    assert loaded.quarantined_at is not None
    history = db2.query(MemoryStatusHistory).filter_by(memory_id=mem.id).count()
    assert history == 1
    assert engine.revert(mem.id) is True
    db2.expire_all()
    loaded = db2.query(Memory).filter_by(id=mem.id).one()
    assert loaded.state == MemoryState.active
    db2.close()
    db.close()


def test_purge_expired_only_old_quarantined(session_factory):
    db = session_factory()
    mem = _memory(db, state=MemoryState.quarantined, suffix="q")
    mem.quarantined_at = datetime.now(UTC) - timedelta(days=40)
    db.commit()
    mem_id = mem.id
    active = _memory(db, state=MemoryState.active, suffix="2")
    active_id = active.id
    db.close()

    engine = QuarantineEngine(session_factory=session_factory, vector_store_provider=lambda: None)
    purged = engine.purge_expired(older_than_days=30, limit=10)
    assert purged == 1

    db2 = session_factory()
    assert db2.query(Memory).filter_by(id=mem_id).first() is None
    assert db2.query(Memory).filter_by(id=active_id).first() is not None
    db2.close()
