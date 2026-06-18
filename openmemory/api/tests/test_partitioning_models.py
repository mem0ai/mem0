"""Tests for the partitioning state model + migration (task_01 / ADR-002 / ADR-003).

Two layers, both runnable without external services:

- model-level unit tests against in-memory SQLite (defaults, enum values,
  NOT NULL enforcement);
- an Alembic upgrade/downgrade round-trip against a temporary on-disk SQLite
  database, exercising the migration DDL cross-dialect.

PostgreSQL-specific assertions live in ``test_postgres_migrations.py`` (gated by
``POSTGRES_TEST_URL``).
"""

import os
from pathlib import Path

# Dummy key before importing app modules that initialize clients.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    MigrationState,
    MigrationStatus,
    PartitionTier,
    Project,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# Enum definitions
# --------------------------------------------------------------------------- #
def test_migration_status_has_exactly_six_values():
    assert {s.value for s in MigrationStatus} == {
        "planned",
        "copying",
        "validating",
        "flipped",
        "rolled_back",
        "done",
    }


def test_partition_tier_has_shared_and_dedicated():
    assert {t.value for t in PartitionTier} == {"shared", "dedicated"}


# --------------------------------------------------------------------------- #
# Project defaults
# --------------------------------------------------------------------------- #
def test_new_project_defaults_to_shared_tier(session):
    session.add(Project(name="proj-a"))
    session.commit()

    proj = session.query(Project).filter_by(name="proj-a").one()
    assert proj.partition_tier == PartitionTier.shared
    assert proj.shard_key is None


def test_project_can_be_promoted_to_dedicated(session):
    session.add(
        Project(name="big", partition_tier=PartitionTier.dedicated, shard_key="big")
    )
    session.commit()

    proj = session.query(Project).filter_by(name="big").one()
    assert proj.partition_tier == PartitionTier.dedicated
    assert proj.shard_key == "big"


# --------------------------------------------------------------------------- #
# MigrationState constraints / defaults
# --------------------------------------------------------------------------- #
def test_migration_state_requires_collections(session):
    # active_collection (and source/target) are NOT NULL.
    session.add(MigrationState(source_collection="blue", target_collection="green"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_migration_state_defaults(session):
    state = MigrationState(
        source_collection="blue",
        target_collection="green",
        active_collection="blue",
    )
    session.add(state)
    session.commit()

    loaded = session.query(MigrationState).one()
    assert loaded.status == MigrationStatus.planned
    assert loaded.dual_write_enabled is False
    assert loaded.scroll_cursor is None


# --------------------------------------------------------------------------- #
# Alembic round-trip (SQLite)
# --------------------------------------------------------------------------- #
def _alembic_config():
    """Build an Alembic Config from the repo's real alembic.ini.

    Using the real ini provides the logging sections that env.py's ``fileConfig``
    requires; ``script_location`` is pinned to an absolute path so it resolves
    regardless of cwd. env.py reads ``DATABASE_URL`` from the environment, so the
    ini's ``sqlalchemy.url`` is irrelevant here.
    """
    from alembic.config import Config

    api_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    return cfg


def test_alembic_round_trip_sqlite(tmp_path, monkeypatch):
    db_file = tmp_path / "roundtrip.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)

    from alembic import command

    cfg = _alembic_config()

    command.upgrade(cfg, "head")
    eng = create_engine(url)
    insp = inspect(eng)
    assert "migration_state" in insp.get_table_names()
    project_cols = {c["name"] for c in insp.get_columns("projects")}
    assert {"partition_tier", "shard_key"} <= project_cols
    eng.dispose()

    command.downgrade(cfg, "-1")
    eng = create_engine(url)
    insp = inspect(eng)
    assert "migration_state" not in insp.get_table_names()
    project_cols = {c["name"] for c in insp.get_columns("projects")}
    assert "partition_tier" not in project_cols
    assert "shard_key" not in project_cols
    eng.dispose()
