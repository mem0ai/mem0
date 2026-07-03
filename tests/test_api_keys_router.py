"""Tests for the api-keys router.

revoke_key takes the key_id straight from the URL path and passes it to
db.get(APIKey, key_id). The id column is a Postgres uuid, so a malformed
(non-UUID) key_id makes psycopg raise a DataError at bind time -- which
surfaces as a 500 -- before the None -> 404 check is ever reached. A missing
key should always be a 404, whether or not the id is a valid UUID.
"""

import os
import sys
import uuid

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import DataError  # noqa: E402

# server/ modules use bare imports (from auth import ...), so the server
# directory itself must be importable, mirroring how it runs in Docker.
_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from auth import require_auth  # noqa: E402
from db import get_db  # noqa: E402
from models import User  # noqa: E402
from routers import api_keys as api_keys_router  # noqa: E402


class _RaisingSession:
    """Stands in for a SQLAlchemy session whose uuid column rejects bad input.

    Postgres raises DataError when a non-UUID string is bound to a uuid
    column; we reproduce that here without needing a live database. A valid
    UUID that maps to no row yields None, the same as a real lookup miss.
    """

    def get(self, _model, ident, *_args, **_kwargs):
        try:
            uuid.UUID(str(ident))
        except ValueError as exc:
            raise DataError("invalid input syntax for type uuid", None, exc) from exc
        return None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api_keys_router.router)

    fake_user = User(id=uuid.uuid4(), name="t", email="t@e.com", password_hash="x", role="admin")
    app.dependency_overrides[require_auth] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: _RaisingSession()

    return TestClient(app, raise_server_exceptions=False)


def test_revoke_malformed_key_id_returns_404(client):
    resp = client.delete("/api-keys/not-a-uuid")
    assert resp.status_code == 404


def test_revoke_missing_valid_uuid_returns_404(client):
    resp = client.delete(f"/api-keys/{uuid.uuid4()}")
    assert resp.status_code == 404
