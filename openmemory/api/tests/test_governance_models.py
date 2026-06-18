"""Tests for governance models + migration (Fase 3 task_01)."""

import os
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    GovernanceJob,
    GovernanceJobStatus,
    GovernanceJobType,
    GovernancePolicy,
    GovernanceSchedule,
    Memory,
    MemoryState,
    Project,
    User,
    App,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _memory(session, state=MemoryState.active, quarantined_at=None):
    user = User(user_id="u1")
    app = App(owner=user, name="app1")
    session.add_all([user, app])
    session.flush()
    mem = Memory(
        user_id=user.id,
        app_id=app.id,
        content="test memory",
        state=state,
        quarantined_at=quarantined_at,
    )
    session.add(mem)
    session.commit()
    return mem


def test_memory_state_includes_quarantined():
    assert MemoryState.quarantined.value == "quarantined"
    assert {s.value for s in MemoryState} >= {
        "active",
        "paused",
        "archived",
        "deleted",
        "quarantined",
    }


def test_memory_quarantined_persists(session):
    from datetime import UTC, datetime

    ts = datetime.now(UTC)
    mem = _memory(session, MemoryState.quarantined, quarantined_at=ts)
    loaded = session.query(Memory).filter_by(id=mem.id).one()
    assert loaded.state == MemoryState.quarantined
    assert loaded.quarantined_at.replace(tzinfo=None) == ts.replace(tzinfo=None)


def test_governance_job_accepts_enums(session):
    job = GovernanceJob(
        job_type=GovernanceJobType.dedup,
        status=GovernanceJobStatus.queued,
    )
    session.add(job)
    session.commit()
    assert session.query(GovernanceJob).count() == 1


def test_governance_policy_requires_project(session):
    session.add(Project(name="proj-a"))
    session.commit()
    session.add(GovernancePolicy(project_name="proj-a", overrides={"ttl_max_age_days": 365}))
    session.commit()
    row = session.query(GovernancePolicy).one()
    assert row.overrides["ttl_max_age_days"] == 365


def test_governance_schedule_composite_pk(session):
    session.add(
        GovernanceSchedule(
            job_type=GovernanceJobType.dedup,
            scope="__global__",
        )
    )
    session.commit()
    with pytest.raises(IntegrityError):
        session.add(
            GovernanceSchedule(
                job_type=GovernanceJobType.dedup,
                scope="__global__",
            )
        )
        session.commit()
    session.rollback()


def _alembic_config():
    from alembic.config import Config

    api_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    return cfg


def test_alembic_round_trip_governance_sqlite(tmp_path, monkeypatch):
    db_file = tmp_path / "gov.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    from alembic import command

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    assert {"governance_jobs", "governance_policies", "governance_schedule"} <= tables
    memory_cols = {c["name"] for c in insp.get_columns("memories")}
    assert "quarantined_at" in memory_cols
    eng.dispose()

    # Downgrade past the governance migration explicitly (revisão anterior à
    # governança) — robusto a migrations adicionadas no topo, como a de
    # quota/cold-tier (a6b7c8d9e0f1).
    command.downgrade(cfg, "e4d5f6a7b8c9")
    eng = create_engine(url)
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    assert "governance_jobs" not in tables
    memory_cols = {c["name"] for c in insp.get_columns("memories")}
    assert "quarantined_at" not in memory_cols
    eng.dispose()


def test_existing_memories_keep_state_after_upgrade(tmp_path, monkeypatch):
    db_file = tmp_path / "preserve.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    from alembic import command

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    Session = sessionmaker(bind=eng)
    db = Session()
    mem = _memory(db, state=MemoryState.active)
    mem_id = mem.id
    db.close()
    eng.dispose()

    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    Session = sessionmaker(bind=eng)
    db = Session()
    loaded = db.query(Memory).filter_by(id=mem_id).one()
    assert loaded.state == MemoryState.active
    assert loaded.quarantined_at is None
    db.close()
    eng.dispose()


# ---------------------------------------------------------------------------
# Quota / cold-tier state (task_04 / ADR-005)
# ---------------------------------------------------------------------------

def test_governance_job_type_has_quota_and_cold_tier():
    from app.models import GovernanceJobType

    assert GovernanceJobType.enforce_quota.value == "enforce_quota"
    assert GovernanceJobType.cold_tier.value == "cold_tier"


def test_schedule_intervals_has_monthly():
    from datetime import timedelta

    from app.workers.governance_worker import SCHEDULE_INTERVALS

    assert SCHEDULE_INTERVALS["monthly"] == timedelta(days=30)


def test_migration_adds_last_activity_at_column(tmp_path, monkeypatch):
    db_file = tmp_path / "act.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    from alembic import command

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("projects")}
    assert "last_activity_at" in cols
    eng.dispose()
