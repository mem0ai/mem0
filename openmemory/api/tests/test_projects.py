"""Tests for the internal project catalog (task_02).

Covers the idempotent ``upsert_project`` helper and the ``projects`` table
against a temporary on-disk SQLite database: first sighting creates a row with
``name`` + ``first_seen_hostname`` (and ``created_at``), repeated sightings are a
no-op (no duplicate, no error), and the table is created/usable via
``Base.metadata`` (``create_all``)/a real session.
"""

import os

# Set dummy keys before importing app modules that initialize clients.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Project
from app.utils.projects import upsert_project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Path to a temporary on-disk SQLite file (durable across connections)."""
    return str(tmp_path / "projects_test.db")


def _make_factory(db_path, create_all=False):
    """Create an engine + sessionmaker bound to a real sqlite file.

    By default only the ``projects`` table is created (avoids pulling unrelated
    FKs). When ``create_all`` is True, the full metadata is created via
    ``Base.metadata.create_all`` to exercise the startup path.
    """
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    if create_all:
        Base.metadata.create_all(bind=engine)
    else:
        Project.__table__.create(bind=engine, checkfirst=True)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, factory


@pytest.fixture
def session(db_path):
    """A real session bound to a temporary sqlite file with the projects table."""
    engine, factory = _make_factory(db_path)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# upsert: creation
# ---------------------------------------------------------------------------

class TestUpsertCreate:
    def test_upsert_creates_row_with_name_and_hostname(self, session):
        project = upsert_project("proj-a", hostname="host-1", session=session)

        assert project.name == "proj-a"
        assert project.first_seen_hostname == "host-1"

        # Row persisted and queryable.
        row = session.query(Project).filter(Project.name == "proj-a").first()
        assert row is not None
        assert row.name == "proj-a"
        assert row.first_seen_hostname == "host-1"

    def test_upsert_sets_created_at(self, session):
        project = upsert_project("proj-created-at", hostname="h", session=session)

        assert project.created_at is not None
        assert isinstance(project.created_at, datetime.datetime)

    def test_upsert_without_hostname(self, session):
        project = upsert_project("proj-no-host", session=session)

        assert project.name == "proj-no-host"
        assert project.first_seen_hostname is None


# ---------------------------------------------------------------------------
# upsert: idempotency
# ---------------------------------------------------------------------------

class TestUpsertIdempotent:
    def test_second_upsert_no_duplicate_no_error(self, session):
        first = upsert_project("dup", hostname="host-1", session=session)
        # Second sighting must not raise and must not create a duplicate.
        second = upsert_project("dup", hostname="host-2", session=session)

        count = session.query(Project).filter(Project.name == "dup").count()
        assert count == 1
        # first_seen_hostname is recorded only on creation.
        assert second.first_seen_hostname == "host-1"
        assert first.name == second.name


# ---------------------------------------------------------------------------
# upsert: last_activity_at (task_04 / ADR-005)
# ---------------------------------------------------------------------------

class TestLastActivity:
    def test_upsert_sets_last_activity_on_create(self, session):
        project = upsert_project("act-create", hostname="h", session=session)
        assert project.last_activity_at is not None
        assert isinstance(project.last_activity_at, datetime.datetime)

    def test_repeated_upsert_advances_last_activity(self, session):
        first = upsert_project("act-touch", hostname="h", session=session)
        t1 = first.last_activity_at
        # A subsequent sighting must refresh the activity timestamp (>= the first).
        second = upsert_project("act-touch", hostname="h", session=session)
        assert second.last_activity_at >= t1

    def test_total_count_after_repeated_upserts(self, session):
        upsert_project("a", hostname="h", session=session)
        upsert_project("a", hostname="h", session=session)
        upsert_project("b", hostname="h", session=session)

        assert session.query(Project).count() == 2


# ---------------------------------------------------------------------------
# upsert: default session (SessionLocal path)
# ---------------------------------------------------------------------------

class TestUpsertDefaultSession:
    def test_upsert_uses_session_local_when_session_omitted(
        self, db_path, monkeypatch
    ):
        engine, factory = _make_factory(db_path)
        # Point the helper's SessionLocal at the temporary database.
        import app.utils.projects as projects_module

        monkeypatch.setattr(projects_module, "SessionLocal", factory)

        upsert_project("via-default", hostname="host-x")
        # Idempotent on the default path too.
        upsert_project("via-default", hostname="host-y")

        db = factory()
        try:
            rows = db.query(Project).filter(Project.name == "via-default").all()
            assert len(rows) == 1
            assert rows[0].first_seen_hostname == "host-x"
        finally:
            db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# integration: table creation via create_all + real upsert
# ---------------------------------------------------------------------------

class TestTableCreation:
    def test_projects_table_exists_after_create_all(self, db_path):
        engine, factory = _make_factory(db_path, create_all=True)
        try:
            inspector = inspect(engine)
            assert "projects" in inspector.get_table_names()

            columns = {c["name"] for c in inspector.get_columns("projects")}
            assert {"name", "created_at", "first_seen_hostname"} <= columns
        finally:
            engine.dispose()

    def test_upsert_via_real_session_after_create_all(self, db_path):
        engine, factory = _make_factory(db_path, create_all=True)
        db = factory()
        try:
            upsert_project("integration", hostname="host-int", session=db)
            row = db.query(Project).filter(
                Project.name == "integration"
            ).first()
            assert row is not None
            assert row.first_seen_hostname == "host-int"
            assert row.created_at is not None
        finally:
            db.close()
            engine.dispose()
