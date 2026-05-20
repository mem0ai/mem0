"""Router-level tests for /api/v1/memories/* covering both:

  * the existing scoped-by-user_id semantics (regression — must not break),
  * the new all-users sentinel semantics (empty / missing user_id returns
    memories from every user).

The tests use an in-memory SQLite database and FastAPI's dependency-override
mechanism to avoid touching the real openmemory.db. They seed two distinct
users (UserA, UserB) each with their own memories so the difference between
"scoped" and "all-users" is observable.
"""

from __future__ import annotations

import os
from uuid import uuid4

# Quiet env-var-required imports inside transitive deps.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import App, Memory, MemoryState, User
from app.routers import memories as memories_router_module
from app.routers.memories import resolve_user_or_none, router as memories_router

# ---------------------------------------------------------------------------
# Test infra
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Fresh in-memory SQLite session per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_db(db_session):
    """Two users, each with two active memories under one app."""
    user_a = User(id=uuid4(), user_id="UserA", name="A")
    user_b = User(id=uuid4(), user_id="UserB", name="B")
    db_session.add_all([user_a, user_b])
    db_session.flush()

    app_a = App(id=uuid4(), name="claude", owner_id=user_a.id)
    app_b = App(id=uuid4(), name="claude", owner_id=user_b.id)
    db_session.add_all([app_a, app_b])
    db_session.flush()

    db_session.add_all([
        Memory(id=uuid4(), user_id=user_a.id, app_id=app_a.id,
               content="A-mem-1", state=MemoryState.active),
        Memory(id=uuid4(), user_id=user_a.id, app_id=app_a.id,
               content="A-mem-2", state=MemoryState.active),
        Memory(id=uuid4(), user_id=user_b.id, app_id=app_b.id,
               content="B-mem-1", state=MemoryState.active),
        Memory(id=uuid4(), user_id=user_b.id, app_id=app_b.id,
               content="B-mem-2", state=MemoryState.active),
        # Soft-deleted: must never appear in any result.
        Memory(id=uuid4(), user_id=user_a.id, app_id=app_a.id,
               content="A-deleted", state=MemoryState.deleted),
    ])
    db_session.commit()
    return db_session


@pytest.fixture
def test_app(seeded_db):
    """FastAPI app with the memories router and get_db wired to seeded_db."""
    app = FastAPI()
    app.include_router(memories_router)
    add_pagination(app)

    def _override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# resolve_user_or_none — pure helper
# ---------------------------------------------------------------------------

def test_resolve_user_or_none_returns_none_for_empty_string(seeded_db):
    assert resolve_user_or_none(seeded_db, "") is None


def test_resolve_user_or_none_returns_none_for_none(seeded_db):
    assert resolve_user_or_none(seeded_db, None) is None


def test_resolve_user_or_none_returns_user_for_valid_id(seeded_db):
    u = resolve_user_or_none(seeded_db, "UserA")
    assert u is not None
    assert u.user_id == "UserA"


def test_resolve_user_or_none_raises_404_for_unknown(seeded_db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        resolve_user_or_none(seeded_db, "NoSuchUser")
    assert ei.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/memories/ — list_memories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_scoped_to_user_a_returns_only_user_a_memories(client):
    resp = await client.get("/api/v1/memories/?user_id=UserA&size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    contents = sorted(m["content"] for m in body["items"])
    assert contents == ["A-mem-1", "A-mem-2"]


@pytest.mark.asyncio
async def test_list_scoped_to_user_b_returns_only_user_b_memories(client):
    resp = await client.get("/api/v1/memories/?user_id=UserB&size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    contents = sorted(m["content"] for m in body["items"])
    assert contents == ["B-mem-1", "B-mem-2"]


@pytest.mark.asyncio
async def test_list_all_users_via_empty_user_id_returns_both(client):
    """Empty user_id is the all-users sentinel: must include both users."""
    resp = await client.get("/api/v1/memories/?user_id=&size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4  # 2 from A, 2 from B, deleted excluded
    contents = sorted(m["content"] for m in body["items"])
    assert contents == ["A-mem-1", "A-mem-2", "B-mem-1", "B-mem-2"]


@pytest.mark.asyncio
async def test_list_all_users_via_omitted_user_id_returns_both(client):
    """Omitting user_id entirely is also the all-users sentinel."""
    resp = await client.get("/api/v1/memories/?size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4


@pytest.mark.asyncio
async def test_list_unknown_user_id_still_returns_404(client):
    """A non-empty but unknown user_id is a typo, not the all-users sentinel."""
    resp = await client.get("/api/v1/memories/?user_id=NoSuchUser")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_does_not_include_deleted_memories_in_all_users_view(client):
    resp = await client.get("/api/v1/memories/?user_id=&size=50")
    assert resp.status_code == 200
    body = resp.json()
    contents = [m["content"] for m in body["items"]]
    assert "A-deleted" not in contents


# ---------------------------------------------------------------------------
# GET /api/v1/memories/categories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_categories_scoped_returns_200_and_list_shape(client):
    resp = await client.get("/api/v1/memories/categories?user_id=UserA")
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body and "total" in body


@pytest.mark.asyncio
async def test_categories_all_users_returns_200_and_list_shape(client):
    resp = await client.get("/api/v1/memories/categories?user_id=")
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body and "total" in body


@pytest.mark.asyncio
async def test_categories_unknown_user_returns_404(client):
    resp = await client.get("/api/v1/memories/categories?user_id=NoSuchUser")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/memories/filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_scoped_to_user_a(client):
    resp = await client.post("/api/v1/memories/filter",
                             json={"user_id": "UserA", "page": 1, "size": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all("A-" in m["content"] for m in body["items"])


@pytest.mark.asyncio
async def test_filter_all_users_via_empty_user_id(client):
    resp = await client.post("/api/v1/memories/filter",
                             json={"user_id": "", "page": 1, "size": 50})
    assert resp.status_code == 200
    body = resp.json()
    # /filter excludes only deleted by default; archived stays unless show_archived
    # — our seed has no archived so all four active memories should appear.
    assert body["total"] == 4


@pytest.mark.asyncio
async def test_filter_all_users_via_omitted_user_id(client):
    resp = await client.post("/api/v1/memories/filter",
                             json={"page": 1, "size": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4


@pytest.mark.asyncio
async def test_filter_unknown_user_returns_404(client):
    resp = await client.post("/api/v1/memories/filter",
                             json={"user_id": "NoSuchUser"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Scoped client wrapper invariant — the all-users mode is SQL-only and never
# constructs a ScopedMemoryClient with empty user_id.
# ---------------------------------------------------------------------------

def test_scoped_client_still_rejects_empty_user_id_after_sentinel_added():
    """The all-users mode is a SQL-side concern only.

    ScopedMemoryClient — which is the boundary for any mem0 vector-store
    operation — must continue to reject empty user_id, because mem0 vector
    operations are always per-user. This test guards against the temptation
    to "support all-users in the wrapper too" later on.
    """
    from app.utils.scoped_client import ScopedMemoryClient

    class _AnyClient:
        def add(self, *a, **kw): pass
        def get_all(self, *a, **kw): pass
        def delete(self, *a, **kw): pass

    with pytest.raises(ValueError, match="non-empty user_id"):
        ScopedMemoryClient(_AnyClient(), "")
    with pytest.raises(ValueError, match="non-empty user_id"):
        ScopedMemoryClient(_AnyClient(), None)  # type: ignore[arg-type]
