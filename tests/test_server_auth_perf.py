"""Regression tests for API-key auth performance (issue #6977).

Two problems, one per test class:

  * ``verify_auth`` ran the API-key resolver — a DB query plus a ~100-300ms
    bcrypt verify — directly on the event loop thread, so a single in-flight
    API-key request stalled every other concurrent request. The fix offloads
    it with ``anyio.to_thread.run_sync``; the test asserts the resolver runs on
    a worker thread, not the loop thread.

  * Migration 007 adds the indexes the auth and key-listing queries rely on.
    The test runs the migration against SQLite and checks the indexes exist
    (and that the ``key_prefix`` one keeps its partial ``WHERE`` predicate).

Neither test needs a live Postgres.
"""

import asyncio
import importlib.util
import os
import sys
import threading

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

# server/ modules use bare imports (from auth import ...), so the server
# directory itself must be importable, mirroring how it runs in Docker.
_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from alembic.operations import Operations  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


# ---------------------------------------------------------------------------
# 1. bcrypt / DB lookup must not run on the event loop thread
# ---------------------------------------------------------------------------

class TestApiKeyResolutionOffloadsEventLoop:
    def test_resolver_runs_off_the_event_loop_thread(self, monkeypatch):
        """verify_auth must dispatch the blocking API-key resolver to a worker
        thread. We record the thread the resolver runs on and compare it to the
        event loop's thread; before the fix they were identical."""
        import auth

        loop_thread_id = {}
        resolver_thread_id = {}

        def fake_resolver(key):
            resolver_thread_id["id"] = threading.get_ident()
            return "sentinel-user"

        monkeypatch.setattr(auth, "_resolve_user_from_api_key_sync", fake_resolver)

        class _Req:
            def __init__(self):
                self.state = type("S", (), {})()

        async def run():
            loop_thread_id["id"] = threading.get_ident()
            return await auth.verify_auth(_Req(), credentials=None, x_api_key="m0sk_" + "a" * 40)

        result = asyncio.run(run())

        assert result == "sentinel-user"
        assert resolver_thread_id["id"] != loop_thread_id["id"], (
            "API-key resolver ran on the event loop thread; bcrypt/DB work must be "
            "offloaded with anyio.to_thread.run_sync so it does not block other requests"
        )

    def test_admin_key_still_short_circuits_without_db(self, monkeypatch):
        """The legacy ADMIN_API_KEY fast path must not touch the resolver."""
        import auth

        monkeypatch.setattr(auth, "ADMIN_API_KEY", "admin-secret")

        def boom(key):  # pragma: no cover - should never run
            raise AssertionError("admin key path must not resolve against the DB")

        monkeypatch.setattr(auth, "_resolve_user_from_api_key_sync", boom)

        class _Req:
            def __init__(self):
                self.state = type("S", (), {})()

        req = _Req()
        result = asyncio.run(auth.verify_auth(req, credentials=None, x_api_key="admin-secret"))
        assert result is None
        assert req.state.auth_type == "admin_api_key"


# ---------------------------------------------------------------------------
# 2. Migration 007 creates the api_keys lookup indexes
# ---------------------------------------------------------------------------

def _load_migration_007():
    path = os.path.join(_SERVER_DIR, "alembic", "versions", "007_api_keys_indexes.py")
    spec = importlib.util.spec_from_file_location("migration_007", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_api_keys_table(conn):
    conn.execute(
        text(
            "CREATE TABLE api_keys ("
            "id TEXT PRIMARY KEY, key_prefix VARCHAR(12), key_hash TEXT, "
            "label VARCHAR(255), created_by TEXT, last_used_at TIMESTAMP, "
            "revoked_at TIMESTAMP, created_at TIMESTAMP)"
        )
    )


class TestMigration007Indexes:
    def test_revision_chains_after_006(self):
        migration = _load_migration_007()
        assert migration.revision == "007"
        assert migration.down_revision == "006"

    def test_upgrade_creates_both_indexes_and_downgrade_removes_them(self):
        migration = _load_migration_007()
        engine = create_engine("sqlite://")
        with engine.connect() as conn:
            _make_api_keys_table(conn)
            ctx = MigrationContext.configure(conn)

            with Operations.context(ctx):
                migration.upgrade()

            indexes = {row[1] for row in conn.execute(text("PRAGMA index_list('api_keys')")).fetchall()}
            assert "ix_api_keys_key_prefix_active" in indexes
            assert "ix_api_keys_created_by" in indexes

            with Operations.context(ctx):
                migration.downgrade()

            indexes_after = {row[1] for row in conn.execute(text("PRAGMA index_list('api_keys')")).fetchall()}
            assert "ix_api_keys_key_prefix_active" not in indexes_after
            assert "ix_api_keys_created_by" not in indexes_after

    def test_key_prefix_index_is_partial_on_live_keys(self):
        """The auth query filters ``revoked_at IS NULL``; the index must carry
        the same predicate so it stays small and is actually used."""
        migration = _load_migration_007()
        engine = create_engine("sqlite://")
        with engine.connect() as conn:
            _make_api_keys_table(conn)
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                migration.upgrade()

            sql = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE name = 'ix_api_keys_key_prefix_active'")
            ).scalar()
            assert sql is not None
            assert "key_prefix" in sql
            assert "revoked_at IS NULL" in sql
