"""Unit tests for access-control resolution (app.utils.acl)."""

import os
import uuid

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AccessControl, App, Memory, MemoryState, User
from app.utils.acl import (
    filter_results_by_acl,
    filter_results_by_active_state,
    get_accessible_memory_ids,
    make_memory_access_checker,
    resolve_accessible_ids,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_user_app(db, app_active=True):
    user = User(id=uuid.uuid4(), user_id="u1")
    app = App(id=uuid.uuid4(), owner_id=user.id, name="client", is_active=app_active)
    db.add_all([user, app])
    db.commit()
    return user, app


def _make_memory(db, user, app, state=MemoryState.active):
    mem = Memory(id=uuid.uuid4(), user_id=user.id, app_id=app.id, content="x", state=state)
    db.add(mem)
    db.commit()
    return mem


# --- filter_results_by_acl (pure) ---

def test_filter_none_returns_all():
    results = [{"id": "a"}, {"id": "b"}]
    assert filter_results_by_acl(results, None) == results


def test_filter_set_keeps_only_allowed():
    results = [{"id": "a"}, {"id": "b"}]
    allowed = {uuid.UUID("00000000-0000-0000-0000-00000000000a")}
    # ids in results are arbitrary strings; only matching string forms pass.
    assert filter_results_by_acl(results, allowed) == []


def test_filter_empty_set_returns_nothing():
    assert filter_results_by_acl([{"id": "a"}], set()) == []


def test_filter_matches_stringified_uuid():
    mid = uuid.uuid4()
    results = [{"id": str(mid)}, {"id": "other"}]
    assert filter_results_by_acl(results, {mid}) == [{"id": str(mid)}]


# --- get_accessible_memory_ids / resolve_accessible_ids ---

def test_no_rules_means_all_accessible(db):
    _, app = _make_user_app(db)
    assert get_accessible_memory_ids(db, app.id) is None
    assert resolve_accessible_ids(db, app) is None


def test_inactive_app_accessible_set_empty(db):
    _, app = _make_user_app(db, app_active=False)
    assert resolve_accessible_ids(db, app) == set()


def test_deny_all_rule(db):
    _, app = _make_user_app(db)
    db.add(AccessControl(id=uuid.uuid4(), subject_type="app", subject_id=app.id,
                         object_type="memory", object_id=None, effect="deny"))
    db.commit()
    assert get_accessible_memory_ids(db, app.id) == set()


def test_specific_allow_rule(db):
    user, app = _make_user_app(db)
    mem = _make_memory(db, user, app)
    db.add(AccessControl(id=uuid.uuid4(), subject_type="app", subject_id=app.id,
                         object_type="memory", object_id=mem.id, effect="allow"))
    db.commit()
    assert get_accessible_memory_ids(db, app.id) == {mem.id}


# --- make_memory_access_checker ---

def test_checker_no_app_id_only_state(db):
    user, app = _make_user_app(db)
    active = _make_memory(db, user, app, MemoryState.active)
    paused = _make_memory(db, user, app, MemoryState.paused)
    checker = make_memory_access_checker(db, None)
    assert checker(active) is True
    assert checker(paused) is False


def test_checker_all_accessible_when_no_rules(db):
    user, app = _make_user_app(db)
    mem = _make_memory(db, user, app)
    checker = make_memory_access_checker(db, app.id)
    assert checker(mem) is True


def test_checker_inactive_app_denies_all(db):
    user, app = _make_user_app(db, app_active=False)
    mem = _make_memory(db, user, app)
    checker = make_memory_access_checker(db, app.id)
    assert checker(mem) is False


def test_checker_reuses_passed_app(db):
    user, app = _make_user_app(db)
    mem = _make_memory(db, user, app)
    # Passing the loaded app should not change the result (and avoids a re-query).
    checker = make_memory_access_checker(db, app.id, app=app)
    assert checker(mem) is True


# --- filter_results_by_active_state (the search state-leak regression guard) ---

def test_active_state_filter_excludes_paused_and_archived(db):
    user, app = _make_user_app(db)
    active = _make_memory(db, user, app, MemoryState.active)
    paused = _make_memory(db, user, app, MemoryState.paused)
    archived = _make_memory(db, user, app, MemoryState.archived)
    deleted = _make_memory(db, user, app, MemoryState.deleted)
    results = [{"id": str(m.id)} for m in (active, paused, archived, deleted)]

    filtered = filter_results_by_active_state(db, user.id, results)

    assert [r["id"] for r in filtered] == [str(active.id)]


def test_active_state_filter_scopes_to_user(db):
    user, app = _make_user_app(db)
    mem = _make_memory(db, user, app, MemoryState.active)
    other = User(id=uuid.uuid4(), user_id="u2")
    db.add(other)
    db.commit()
    # A memory id that belongs to a different user must not pass even if active.
    results = [{"id": str(mem.id)}]
    assert filter_results_by_active_state(db, other.id, results) == []


def test_active_state_filter_handles_empty_and_bad_ids(db):
    user, _ = _make_user_app(db)
    assert filter_results_by_active_state(db, user.id, []) == []
    assert filter_results_by_active_state(db, user.id, [{"id": "not-a-uuid"}]) == []
