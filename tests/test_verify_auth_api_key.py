"""Regression tests for the REST API auth hot path (issue #6977).

Two compounding problems in verify_auth's X-API-Key flow:
  1. api_keys.key_prefix had no index -- every authenticated request full-scanned
     api_keys (`WHERE key_prefix = ? AND revoked_at IS NULL`). The model now
     declares the index and migration 007 creates it with IF NOT EXISTS semantics.
  2. bcrypt verification (verify_api_key_hash) ran synchronously inside async
     verify_auth, blocking the event loop ~100-300ms per request. It now runs
     via asyncio.get_running_loop().run_in_executor(None, ...), matching the
     pattern already used for request-log persistence in server/main.py.

The executor-offload tests prove verification executes off the event loop while
the semantic tests pin success/failure behavior as unchanged.
"""

import asyncio
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")
pytest.importorskip("passlib", reason="passlib not installed")

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# server/ modules use bare imports (from auth import ...), so the server
# directory itself must be importable, mirroring how it runs in Docker.
_SERVER_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "server"))
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import auth  # noqa: E402
from db import get_db  # noqa: E402
from models import APIKey, Base, User  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _pin_auth_env(monkeypatch):
    """Deterministic module state regardless of the developer's shell env."""
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(auth, "ADMIN_API_KEY", "")


@pytest.fixture
def session_factory():
    # Shared in-memory DB across threads: TestClient runs the ASGI app on a
    # portal thread, so a plain sqlite:// pool would hand each thread its own
    # empty database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def admin_user(session_factory):
    with session_factory() as db:
        user = User(name="admin", email="admin@example.com", password_hash="x", role="admin")
        db.add(user)
        db.commit()
        return user


def _add_key(session_factory, *, prefix, key_hash, created_by, revoked_at=None):
    with session_factory() as db:
        db.add(APIKey(key_prefix=prefix, key_hash=key_hash, label="t", created_by=created_by, revoked_at=revoked_at))
        db.commit()


@pytest.fixture
def client(session_factory):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(request: Request, user=Depends(auth.verify_auth)):
        return {"email": getattr(user, "email", None), "auth_type": request.state.auth_type}

    def _override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


# ---------------------------------------------------------------------------
# Index existence (schema-level)
# ---------------------------------------------------------------------------

class TestPrefixIndexSchema:
    def test_model_declares_index_on_key_prefix(self):
        indexes = {ix.name: tuple(col.name for col in ix.columns) for ix in APIKey.__table__.indexes}
        assert indexes.get("ix_api_keys_key_prefix") == ("key_prefix",)

    @pytest.mark.parametrize(
        "fn,expected_ddl",
        [
            ("upgrade", "CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON api_keys (key_prefix)"),
            ("downgrade", "DROP INDEX IF EXISTS ix_api_keys_key_prefix"),
        ],
    )
    def test_migration_emits_if_not_exists_ddl(self, fn, expected_ddl):
        pytest.importorskip("alembic", reason="alembic not installed")
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy.dialects import postgresql

        path = _SERVER_DIR / "alembic" / "versions" / "007_api_key_prefix_index.py"
        spec = importlib.util.spec_from_file_location("_mig_007_api_key_prefix_index", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        buffer = StringIO()
        ctx = MigrationContext.configure(dialect=postgresql.dialect(), opts={"as_sql": True, "output_buffer": buffer})
        operations = Operations(ctx)
        original_op = module.op
        module.op = operations
        try:
            getattr(module, fn)()
        finally:
            module.op = original_op

        assert expected_ddl in buffer.getvalue()


# ---------------------------------------------------------------------------
# Executor offload
# ---------------------------------------------------------------------------

class TestBcryptRunsOffEventLoop:
    def test_verify_api_key_hash_runs_outside_event_loop(self, client, session_factory, admin_user):
        full_key, prefix, key_hash = auth.generate_api_key()
        _add_key(session_factory, prefix=prefix, key_hash=key_hash, created_by=admin_user.id)

        observed = {}
        real_verify = auth.verify_api_key_hash

        def spy(plain_key, hashed):
            try:
                asyncio.get_running_loop()
                observed["running_loop"] = True
            except RuntimeError:
                # Worker threads never own a running event loop.
                observed["running_loop"] = False
            return real_verify(plain_key, hashed)

        with patch.object(auth, "verify_api_key_hash", side_effect=spy):
            resp = client.get("/whoami", headers={"X-API-Key": full_key})

        assert resp.status_code == 200
        assert "running_loop" in observed, "bcrypt verification was never invoked"
        assert observed["running_loop"] is False

    def test_candidates_tried_sequentially_until_match(self, client, session_factory, admin_user):
        good_full, good_prefix, good_hash = auth.generate_api_key()
        decoy_full = good_full[:-1] + ("A" if good_full[-1] != "A" else "B")
        _add_key(session_factory, prefix=good_prefix, key_hash=auth.hash_password(decoy_full), created_by=admin_user.id)
        _add_key(session_factory, prefix=good_prefix, key_hash=good_hash, created_by=admin_user.id)

        calls = []
        real_verify = auth.verify_api_key_hash

        with patch.object(auth, "verify_api_key_hash", side_effect=lambda p, h: calls.append(p) or real_verify(p, h)):
            resp = client.get("/whoami", headers={"X-API-Key": good_full})

        assert resp.status_code == 200
        assert calls == [decoy_full, good_full]


# ---------------------------------------------------------------------------
# Auth semantics preserved
# ---------------------------------------------------------------------------

class TestAuthSemanticsPreserved:
    def test_valid_api_key_authenticates(self, client, session_factory, admin_user):
        full_key, prefix, key_hash = auth.generate_api_key()
        _add_key(session_factory, prefix=prefix, key_hash=key_hash, created_by=admin_user.id)

        resp = client.get("/whoami", headers={"X-API-Key": full_key})

        assert resp.status_code == 200
        assert resp.json() == {"email": "admin@example.com", "auth_type": "api_key"}

    def test_unknown_key_rejected(self, client):
        resp = client.get("/whoami", headers={"X-API-Key": "m0sk_" + "z" * 43})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key."

    def test_matching_prefix_but_wrong_secret_rejected(self, client, session_factory, admin_user):
        full_key, prefix, _ = auth.generate_api_key()
        decoy_full = full_key[:-1] + ("A" if full_key[-1] != "A" else "B")
        _add_key(session_factory, prefix=prefix, key_hash=auth.hash_password(decoy_full), created_by=admin_user.id)

        resp = client.get("/whoami", headers={"X-API-Key": full_key})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key."

    def test_revoked_key_rejected(self, client, session_factory, admin_user):
        full_key, prefix, key_hash = auth.generate_api_key()
        _add_key(
            session_factory,
            prefix=prefix,
            key_hash=key_hash,
            created_by=admin_user.id,
            revoked_at=datetime.now(timezone.utc),
        )

        resp = client.get("/whoami", headers={"X-API-Key": full_key})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key."

    def test_missing_owner_returns_owner_not_found(self, client, session_factory, admin_user):
        full_key, prefix, key_hash = auth.generate_api_key()
        _add_key(session_factory, prefix=prefix, key_hash=key_hash, created_by=uuid.uuid4())

        resp = client.get("/whoami", headers={"X-API-Key": full_key})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "API key owner not found."

    def test_legacy_admin_api_key_short_circuit_unchanged(self, client, monkeypatch):
        monkeypatch.setattr(auth, "ADMIN_API_KEY", "legacy-admin-key-123456")

        resp = client.get("/whoami", headers={"X-API-Key": "legacy-admin-key-123456"})

        assert resp.status_code == 200
        assert resp.json() == {"email": None, "auth_type": "admin_api_key"}

    def test_no_credentials_returns_401(self, client):
        resp = client.get("/whoami")

        assert resp.status_code == 401
