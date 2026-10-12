"""Regression tests: a password change (and an explicit logout) must revoke the
user's existing refresh tokens, so a session cannot outlive the credential that
created it (CWE-613).

The repo has no DB-backed harness for the JWT/refresh flow, so this builds a
minimal one: the real auth router/models/helpers, with get_db overridden onto a
throwaway SQLite database.
"""
import os
import sys
import uuid

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import sqltypes

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MEM0_TELEMETRY", "false")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

# Postgres coerces str -> UUID on bind; SQLite's Uuid type raises on a str.
# Mimic Postgres so the unmodified server code (which passes string `sub`s) runs.
_orig_bind = sqltypes.Uuid.bind_processor


def _bind(self, dialect):
    proc = _orig_bind(self, dialect)
    if proc is None:
        return None
    return lambda v: proc(uuid.UUID(v) if isinstance(v, str) else v)


sqltypes.Uuid.bind_processor = _bind


@pytest.fixture
def client():
    from db import Base, get_db
    import models  # noqa: F401  (registers tables on Base)
    from rate_limit import limiter
    from routers.auth import router

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    # verify_auth and the token helpers call SessionLocal directly (not get_db),
    # so point the real module-level factory at the test engine as well.
    import auth as auth_mod
    import db as db_mod
    auth_mod.SessionLocal = TestingSession
    db_mod.SessionLocal = TestingSession

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)
    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


def _register(client):
    r = client.post("/auth/register", json={"name": "A", "email": "a@x.com", "password": "OriginalPass1"})
    assert r.status_code == 200, r.text
    return r.json()


def test_password_change_revokes_existing_refresh_tokens(client):
    tok = _register(client)
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {tok['access_token']}"},
        json={"current_password": "OriginalPass1", "new_password": "BrandNewPass2"},
    )
    assert r.status_code == 200
    # The refresh token issued before the change must no longer work.
    r = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 401, "pre-change refresh token should be revoked"


def test_logout_revokes_refresh_token(client):
    tok = _register(client)
    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert r.status_code == 200
    r = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 401, "refresh token should be revoked after logout"


def test_refresh_still_works_without_change_or_logout(client):
    tok = _register(client)
    r = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 200, "a normal refresh must keep working"
