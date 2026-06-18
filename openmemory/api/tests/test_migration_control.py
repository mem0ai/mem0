"""Tests for migration control: start/validate/flip/rollback (task_07 / ADR-003).

Drives MigrationControl against SQLite with a fake count function and a real
PartitionResolver, asserting parity gating, atomic flip, resolver invalidation,
and reversibility. No Qdrant required.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.utils.migration_control import MigrationControl, MigrationError
from app.utils.partitioning import PartitionResolver


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _control(factory, counts=None, resolver=None):
    counts = counts or {}
    return MigrationControl(
        session_factory=factory,
        count_fn=lambda c: counts.get(c, 0),
        resolver=resolver or PartitionResolver(session_factory=factory, default_collection="blue"),
    )


def test_start_plans_migration_and_enables_dual_write(factory):
    resolver = PartitionResolver(session_factory=factory, default_collection="blue")
    control = _control(factory, resolver=resolver)

    state = control.start("blue", "green")

    assert state["active_collection"] == "blue"
    assert state["dual_write_enabled"] is True
    assert state["status"] == "planned"
    # Resolver reflects active=blue + dual-write target=green after invalidation.
    assert resolver.active_collection() == "blue"
    assert resolver.dual_write_target() == "green"


def test_start_rejects_same_source_and_target(factory):
    with pytest.raises(MigrationError):
        _control(factory).start("blue", "blue")


def test_start_is_idempotent_single_row(factory):
    control = _control(factory)
    control.start("blue", "green")
    control.start("blue", "green2")
    db = factory()
    try:
        from app.models import MigrationState
        rows = db.query(MigrationState).all()
        assert len(rows) == 1
        assert rows[0].target_collection == "green2"
    finally:
        db.close()


def test_validate_ok_when_target_caught_up(factory):
    control = _control(factory, counts={"blue": 100, "green": 100})
    control.start("blue", "green")
    report = control.validate()
    assert report["ok"] is True
    assert report["source_count"] == 100
    assert report["target_count"] == 100


def test_validate_not_ok_when_target_behind(factory):
    control = _control(factory, counts={"blue": 100, "green": 80})
    control.start("blue", "green")
    assert control.validate()["ok"] is False


def test_flip_repoints_active_and_invalidates(factory):
    resolver = PartitionResolver(session_factory=factory, default_collection="blue")
    control = _control(factory, counts={"blue": 100, "green": 100}, resolver=resolver)
    control.start("blue", "green")
    assert resolver.active_collection() == "blue"

    state = control.flip()

    assert state["active_collection"] == "green"
    assert state["dual_write_enabled"] is False
    assert state["status"] == "flipped"
    # Resolver was invalidated -> serves the new active collection.
    assert resolver.active_collection() == "green"
    assert resolver.dual_write_target() is None


def test_flip_blocked_when_parity_fails(factory):
    resolver = PartitionResolver(session_factory=factory, default_collection="blue")
    control = _control(factory, counts={"blue": 100, "green": 50}, resolver=resolver)
    control.start("blue", "green")

    with pytest.raises(MigrationError):
        control.flip()
    # Active unchanged.
    assert resolver.active_collection() == "blue"


def test_rollback_repoints_to_source(factory):
    resolver = PartitionResolver(session_factory=factory, default_collection="blue")
    control = _control(factory, counts={"blue": 100, "green": 100}, resolver=resolver)
    control.start("blue", "green")
    control.flip()
    assert resolver.active_collection() == "green"

    state = control.rollback()
    assert state["active_collection"] == "blue"
    assert state["status"] == "rolled_back"
    assert resolver.active_collection() == "blue"


def test_flip_before_start_raises(factory):
    with pytest.raises(MigrationError):
        _control(factory, counts={}).flip()
