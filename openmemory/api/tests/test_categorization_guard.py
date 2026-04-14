"""Tests for the skip_categorization guard and _run_categorization in app.models."""

import os

# Set a dummy key before imports that initialize the OpenAI client.
os.environ.setdefault("OPENAI_API_KEY", "dummy")

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """In-memory SQLite DB with all tables created and event listeners registered."""
    import app.models  # noqa: F401 — registers after_insert / after_update listeners
    from app.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def test_user(db):
    from app.models import User

    user = User(user_id="guard_test_user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def test_app_obj(db, test_user):
    from app.models import App

    app_obj = App(name="guard_test_app", owner_id=test_user.id)
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_obj


# ---------------------------------------------------------------------------
# skip_categorization flag (via ORM event)
# ---------------------------------------------------------------------------


class TestSkipCategorizationFlag:
    def test_skip_flag_prevents_categorization(self, db, test_user, test_app_obj):
        """Memory with skip_categorization=True → categorize_memory is NOT called."""
        from app.models import Memory, MemoryState

        with patch("app.models.categorize_memory") as mock_cat:
            memory = Memory(
                user_id=test_user.id,
                app_id=test_app_obj.id,
                content="Test memory with skip flag",
                state=MemoryState.active,
            )
            memory.skip_categorization = True
            db.add(memory)
            db.commit()

        mock_cat.assert_not_called()

    def test_no_skip_flag_with_valid_key_spawns_thread(
        self, db, test_user, test_app_obj, monkeypatch
    ):
        """Memory without skip_categorization + real-looking key → thread is spawned."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-looks-real-abc123")

        from app.models import Memory, MemoryState

        with patch("threading.Thread") as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance

            memory = Memory(
                user_id=test_user.id,
                app_id=test_app_obj.id,
                content="Thread-spawning memory",
                state=MemoryState.active,
            )
            db.add(memory)
            db.commit()

        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()


# ---------------------------------------------------------------------------
# _run_categorization guard logic (unit tests — no DB required)
# ---------------------------------------------------------------------------


class TestRunCategorizationGuard:
    def test_dummy_key_returns_without_spawning_thread(self, monkeypatch):
        """OPENAI_API_KEY=dummy → _run_categorization is a no-op."""
        monkeypatch.setenv("OPENAI_API_KEY", "dummy")

        from app.models import _run_categorization

        with patch("threading.Thread") as mock_thread:
            _run_categorization(MagicMock(), MagicMock())

        mock_thread.assert_not_called()

    def test_missing_key_returns_without_spawning_thread(self, monkeypatch):
        """No OPENAI_API_KEY → _run_categorization is a no-op."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from app.models import _run_categorization

        with patch("threading.Thread") as mock_thread:
            _run_categorization(MagicMock(), MagicMock())

        mock_thread.assert_not_called()

    def test_valid_key_spawns_daemon_thread(self, monkeypatch):
        """A real-looking API key → a daemon thread is created and started."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-looks-real-xyz789")

        from app.models import _run_categorization

        with patch("threading.Thread") as mock_thread:
            mock_instance = MagicMock()
            mock_thread.return_value = mock_instance

            _run_categorization(MagicMock(), MagicMock())

        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()
