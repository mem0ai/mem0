"""Tests for POST /api/v1/memories/ using a mocked Mem0 memory client.

Exercises persistence of ADD and UPDATE events returned by memory_client.add()
into the SQL-backed Memory model.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import App, Memory, MemoryState, MemoryStatusHistory, User
from app.routers.memories import router


def _make_test_client(session):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def session():
    # Single SQLite connection for :memory: so TestClient + ORM share one DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def no_memory_categorization():
    with patch("app.models.categorize_memory", MagicMock(return_value=None)):
        yield


@pytest.fixture
def seeded_user_app(session):
    uid = uuid4()
    user = User(id=uid, user_id="sync-test-user", name="Sync Test")
    aid = uuid4()
    app_row = App(id=aid, owner_id=uid, name="openmemory", is_active=True)
    session.add_all([user, app_row])
    session.commit()
    session.refresh(user)
    session.refresh(app_row)
    return user, app_row


def test_post_memories_update_event_updates_sql_row(session, seeded_user_app):
    """When Mem0 returns UPDATE, the existing memory row content is updated in SQL."""
    user, app_row = seeded_user_app
    mid = uuid4()
    session.add(
        Memory(
            id=mid,
            user_id=user.id,
            app_id=app_row.id,
            content="My age is 41",
            state=MemoryState.active,
        )
    )
    session.commit()

    mock_mc = MagicMock()
    mock_mc.add.return_value = {
        "results": [
            {
                "id": str(mid),
                "memory": "My age is 43",
                "event": "UPDATE",
            }
        ]
    }

    client = _make_test_client(session)
    with patch("app.routers.memories.get_memory_client", return_value=mock_mc):
        r = client.post(
            "/api/v1/memories/",
            json={
                "user_id": "sync-test-user",
                "text": "Actually my age is 43",
                "infer": False,
                "app": "openmemory",
            },
        )

    assert r.status_code == 200
    row = session.query(Memory).filter(Memory.id == mid).first()
    assert row is not None
    assert row.content == "My age is 43"
    hist = (
        session.query(MemoryStatusHistory)
        .filter(MemoryStatusHistory.memory_id == mid)
        .order_by(MemoryStatusHistory.changed_at.desc())
        .first()
    )
    assert hist is not None
    assert hist.old_state == MemoryState.active
    assert hist.new_state == MemoryState.active


def test_post_memories_add_event_inserts_sql_row(session, seeded_user_app):
    """When Mem0 returns ADD, a new memory row is inserted in SQL."""
    user, app_row = seeded_user_app
    new_id = uuid4()
    mock_mc = MagicMock()
    mock_mc.add.return_value = {
        "results": [
            {
                "id": str(new_id),
                "memory": "Favorite color is blue",
                "event": "ADD",
            }
        ]
    }

    client = _make_test_client(session)
    with patch("app.routers.memories.get_memory_client", return_value=mock_mc):
        r = client.post(
            "/api/v1/memories/",
            json={
                "user_id": "sync-test-user",
                "text": "I like blue",
                "infer": False,
                "app": "openmemory",
            },
        )

    assert r.status_code == 200
    row = session.query(Memory).filter(Memory.id == new_id).first()
    assert row is not None
    assert row.content == "Favorite color is blue"
