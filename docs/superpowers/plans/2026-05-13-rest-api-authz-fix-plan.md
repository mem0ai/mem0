# REST API Authorization Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin-gate six routes in mem0's self-hosted OSS REST server, add an inside-route guard on `GET /memories`, surgically fix the docs/code mismatch in `docs/open-source/features/rest-api.mdx`, and stand up a minimal `server/tests/` pytest scaffold — without regressing any of the four supported deployment modes (single-admin JWT, single-admin per-user key, legacy `ADMIN_API_KEY` env, `AUTH_DISABLED=true`).

**Architecture:** One new helper (`_ensure_admin`) and one FastAPI dependency (`require_admin`) in `server/auth.py`. Swap `Depends(verify_auth)` → `Depends(require_admin)` on six routes across three files. Add one inside-route guard on the no-filter branch of `GET /memories`. Surgical edits to four lines in the docs. Pytest scaffold uses SQLite in-memory + `MagicMock` for the memory backend — no Postgres, no pgvector, no Docker required for tests. No DB migration, no SDK changes, no payload schema changes.

**Tech Stack:** Python 3.11, FastAPI 0.115, SQLAlchemy 2.x (DeclarativeBase), SQLite (test-only), pytest, httpx (FastAPI TestClient), unittest.mock. Reuse existing project conventions in `server/`.

**Spec:** `docs/superpowers/specs/2026-05-13-rest-api-authz-fix-design.md` (commit `8f285c75`).

---

## File Map

**Create:**

| Path | Responsibility |
|---|---|
| `server/tests/__init__.py` | empty package marker |
| `server/tests/conftest.py` | pytest fixtures: SQLite engine, TestClient, admin/non-admin User, JWT helpers, env-var monkeypatches |
| `server/tests/test_auth_helpers.py` | unit tests for `_ensure_admin` (sync) and integration tests for `require_admin` via a throwaway probe route |
| `server/tests/test_admin_gating.py` | integration tests for the six admin-gated routes + inside-route guard |
| `server/tests/test_unchanged_routes.py` | regression tests for memory CRUD and `/api-keys/*` |
| `server/requirements-dev.txt` | pytest, pytest-asyncio, httpx |
| `.github/workflows/server-ci.yml` | pytest CI on PRs touching `server/` |

**Modify:**

| Path | Change |
|---|---|
| `server/auth.py` | append `_ensure_admin` + `require_admin` |
| `server/main.py` | swap dep on `GET /configure`, `POST /configure`, `POST /reset`; refactor `GET /memories` for inside-route guard |
| `server/routers/entities.py` | swap dep on `GET /entities` and `DELETE /entities/{type}/{id}`; import `require_admin` |
| `server/routers/requests.py` | swap dep on `GET /requests`; drop unused `user` parameter; trim imports |
| `docs/open-source/features/rest-api.mdx` | surgical line edits (lines 134, 185, endpoint tables, 267) |

---

## Task 1: Pytest scaffold for `server/`

**Files:**
- Create: `server/tests/__init__.py`
- Create: `server/requirements-dev.txt`
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_smoke.py` (deleted at end of task — used only to prove scaffold works)

- [ ] **Step 1: Create the test package marker**

```bash
mkdir -p server/tests
```

Write `server/tests/__init__.py`:

```python
```

(Empty file. Marks `server/tests` as a package.)

- [ ] **Step 2: Create the dev-deps file**

Write `server/requirements-dev.txt`:

```text
-r requirements.txt

pytest>=8.0,<9.0
pytest-asyncio>=0.23,<1.0
httpx>=0.27,<1.0
```

- [ ] **Step 3: Install dev deps locally**

Run: `pip install -r server/requirements-dev.txt`
Expected: clean install, no errors.

- [ ] **Step 4: Create the conftest with shared fixtures**

Write `server/tests/conftest.py`:

```python
"""Shared pytest fixtures for server/ tests.

Strategy:
- SQLite in-memory engine for the auth DB (Users, APIKey, RefreshTokenJti, etc).
- get_memory_instance() is patched to return a MagicMock so routes that touch
  the memory backend don't need pgvector.
- The FastAPI app is imported lazily after env vars are set so module-level
  constants in server.auth (JWT_SECRET, AUTH_DISABLED, ADMIN_API_KEY) bind
  to the test values, not whatever the host shell has.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make server/ importable as a top-level package (matches uvicorn's CWD).
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

# Required for JWT issuance during tests.
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-" + "x" * 32)
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("POSTGRES_HOST", "localhost")  # silence db url builder


@pytest.fixture
def test_engine():
    """Fresh in-memory SQLite engine per test (no cross-test pollution)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Import Base AFTER env vars are set.
    from db import Base  # noqa: E402

    # Importing models registers them on Base.metadata.
    import models  # noqa: F401, E402

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def mock_memory():
    """A MagicMock standing in for the global Memory instance."""
    mock = MagicMock()
    mock.get_all.return_value = {"results": []}
    mock.search.return_value = {"results": []}
    mock.add.return_value = {"results": [], "events": []}
    mock.get.return_value = {"id": "memory-id", "memory": "stub"}
    mock.history.return_value = []
    mock.delete.return_value = None
    mock.delete_all.return_value = None
    mock.reset.return_value = None
    mock.vector_store.list.return_value = [[]]
    return mock


@pytest.fixture
def client(test_session_factory, mock_memory, monkeypatch):
    """FastAPI TestClient with overridden DB session and mocked memory instance."""
    from db import get_db  # noqa: E402
    import server_state  # noqa: E402

    monkeypatch.setattr(server_state, "get_memory_instance", lambda: mock_memory)

    from main import app  # noqa: E402

    # Also patch the binding inside main.py since it imported get_memory_instance by name.
    monkeypatch.setattr("main.get_memory_instance", lambda: mock_memory)

    def _override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session(test_session_factory):
    """A direct DB session for tests that need to insert User rows."""
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


def _make_user(db_session, *, role: str, email: str | None = None):
    from auth import hash_password
    from models import User

    user = User(
        id=uuid.uuid4(),
        name=f"{role}-user",
        email=email or f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("test-password-123"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    return _make_user(db_session, role="admin")


@pytest.fixture
def member_user(db_session):
    """Non-admin User. No public endpoint produces these today; we insert directly."""
    return _make_user(db_session, role="member")


@pytest.fixture
def admin_jwt(admin_user):
    from auth import create_access_token

    return create_access_token(str(admin_user.id), admin_user.role)


@pytest.fixture
def member_jwt(member_user):
    from auth import create_access_token

    return create_access_token(str(member_user.id), member_user.role)


@pytest.fixture
def auth_admin_header(admin_jwt):
    return {"Authorization": f"Bearer {admin_jwt}"}


@pytest.fixture
def auth_member_header(member_jwt):
    return {"Authorization": f"Bearer {member_jwt}"}


@pytest.fixture
def admin_api_key_env(monkeypatch):
    """Activates the legacy ADMIN_API_KEY escape hatch."""
    import auth

    key = "admin-api-key-test-value-" + "y" * 16
    monkeypatch.setattr(auth, "ADMIN_API_KEY", key)
    return {"X-API-Key": key}


@pytest.fixture
def auth_disabled_env(monkeypatch):
    """Activates AUTH_DISABLED=true."""
    import auth

    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    return {}  # no headers needed
```

- [ ] **Step 5: Add a smoke test to prove the scaffold loads**

Write `server/tests/test_smoke.py`:

```python
def test_scaffold_imports(client):
    """Asserts the TestClient fixture wires up cleanly."""
    response = client.get("/auth/setup-status")
    assert response.status_code == 200
    assert response.json() == {"needsSetup": True}
```

- [ ] **Step 6: Run the smoke test**

Run: `cd server && pytest tests/test_smoke.py -v`
Expected: `1 passed`. If imports fail, fix the `sys.path` insert in conftest.py and re-run.

- [ ] **Step 7: Delete the smoke test (scaffold proven)**

```bash
rm server/tests/test_smoke.py
```

- [ ] **Step 8: Commit**

```bash
git add server/tests/__init__.py server/tests/conftest.py server/requirements-dev.txt
git commit -m "test(server): add pytest scaffold with SQLite + mocked memory backend"
```

---

## Task 2: `_ensure_admin` and `require_admin` (TDD)

**Files:**
- Create: `server/tests/test_auth_helpers.py`
- Modify: `server/auth.py` (append at end of file)

- [ ] **Step 1: Write the failing tests**

Write `server/tests/test_auth_helpers.py`:

```python
"""Unit tests for _ensure_admin and require_admin in server/auth.py."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def _fake_request(auth_type: str = "none"):
    return SimpleNamespace(state=SimpleNamespace(auth_type=auth_type))


def test_ensure_admin_passes_for_admin_user(admin_user):
    from auth import _ensure_admin

    _ensure_admin(_fake_request("bearer"), admin_user)  # must not raise


def test_ensure_admin_passes_for_admin_api_key_auth_type():
    from auth import _ensure_admin

    _ensure_admin(_fake_request("admin_api_key"), None)  # must not raise


def test_ensure_admin_passes_for_auth_disabled():
    from auth import _ensure_admin

    _ensure_admin(_fake_request("disabled"), None)  # must not raise


def test_ensure_admin_rejects_non_admin_user(member_user):
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("bearer"), member_user)
    assert exc.value.status_code == 403
    assert "Admin role required" in exc.value.detail


def test_ensure_admin_rejects_no_user_with_no_legacy_path():
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("none"), None)
    assert exc.value.status_code == 403


def test_ensure_admin_rejects_bearer_with_no_user():
    """Defense-in-depth: a 'bearer' auth_type without a User should not pass."""
    from auth import _ensure_admin

    with pytest.raises(HTTPException) as exc:
        _ensure_admin(_fake_request("bearer"), None)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `cd server && pytest tests/test_auth_helpers.py -v`
Expected: 6 errors (`ImportError: cannot import name '_ensure_admin' from 'auth'`).

- [ ] **Step 3: Implement `_ensure_admin` and `require_admin`**

Edit `server/auth.py`. Append at the end of the file (after the existing `require_auth` function):

```python


def _ensure_admin(request: Request, user: User | None) -> None:
    """Single source of truth for admin gating.

    Allows: legacy ADMIN_API_KEY env (X-API-Key header), AUTH_DISABLED=true,
    or a registered User with role == 'admin'. Raises 403 otherwise.

    Pure function — reusable from FastAPI deps and inline route guards.
    """
    auth_type = getattr(request.state, "auth_type", "none")
    if auth_type in {"admin_api_key", "disabled"}:
        return
    if user is not None and user.role == "admin":
        return
    raise HTTPException(status_code=403, detail="Admin role required.")


async def require_admin(
    request: Request,
    user: User | None = Depends(verify_auth),
) -> None:
    """FastAPI dependency. Admin-only gate; returns nothing."""
    _ensure_admin(request, user)
```

- [ ] **Step 4: Run tests, confirm they pass**

Run: `cd server && pytest tests/test_auth_helpers.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add server/auth.py server/tests/test_auth_helpers.py
git commit -m "feat(server): add _ensure_admin helper and require_admin FastAPI dep"
```

---

## Task 3: Admin-gate `GET /configure` and `POST /configure`

**Files:**
- Create: `server/tests/test_admin_gating.py`
- Modify: `server/main.py:303-318`

- [ ] **Step 1: Write the failing tests**

Write `server/tests/test_admin_gating.py`:

```python
"""Integration tests for admin-gated routes.

Covers, for each affected route, the regression matrix:
- admin JWT       -> success
- ADMIN_API_KEY   -> success (no DB user required)
- AUTH_DISABLED   -> success
- member JWT      -> 403
- no auth         -> 401
"""

from __future__ import annotations

import pytest


# --- GET /configure ---


def test_get_configure_admin_jwt(client, auth_admin_header):
    response = client.get("/configure", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_configure_admin_api_key(client, admin_api_key_env):
    response = client.get("/configure", headers=admin_api_key_env)
    assert response.status_code == 200


def test_get_configure_auth_disabled(client, auth_disabled_env):
    response = client.get("/configure")
    assert response.status_code == 200


def test_get_configure_member_forbidden(client, auth_member_header):
    response = client.get("/configure", headers=auth_member_header)
    assert response.status_code == 403


def test_get_configure_no_auth_unauthorized(client):
    response = client.get("/configure")
    assert response.status_code == 401


# --- POST /configure ---


def _valid_config():
    return {
        "vector_store": {"provider": "pgvector", "config": {"host": "h"}},
        "llm": {"provider": "openai", "config": {"api_key": "x", "model": "m"}},
        "embedder": {"provider": "openai", "config": {"api_key": "x", "model": "e"}},
    }


def test_post_configure_admin_jwt(client, auth_admin_header):
    response = client.post("/configure", headers=auth_admin_header, json=_valid_config())
    assert response.status_code == 200


def test_post_configure_admin_api_key(client, admin_api_key_env):
    response = client.post("/configure", headers=admin_api_key_env, json=_valid_config())
    assert response.status_code == 200


def test_post_configure_auth_disabled(client, auth_disabled_env):
    response = client.post("/configure", json=_valid_config())
    assert response.status_code == 200


def test_post_configure_member_forbidden(client, auth_member_header):
    response = client.post("/configure", headers=auth_member_header, json=_valid_config())
    assert response.status_code == 403


def test_post_configure_no_auth_unauthorized(client):
    response = client.post("/configure", json=_valid_config())
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests, confirm member tests FAIL with 200 instead of 403**

Run: `cd server && pytest tests/test_admin_gating.py::test_get_configure_member_forbidden tests/test_admin_gating.py::test_post_configure_member_forbidden -v`
Expected: both FAIL with `assert 200 == 403` (the routes currently accept any authenticated caller).

- [ ] **Step 3: Swap the dep on both `/configure` routes**

Edit `server/main.py`. Change lines 303-305 (`GET /configure`):

From:
```python
@app.get("/configure", summary="Get current Mem0 configuration")
def get_config(_auth=Depends(verify_auth)):
    return _redact_config(get_current_config())
```

To:
```python
@app.get("/configure", summary="Get current Mem0 configuration")
def get_config(_admin=Depends(require_admin)):
    return _redact_config(get_current_config())
```

Change lines 313-318 (`POST /configure`):

From:
```python
@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any], _auth=Depends(verify_auth)):
    """Set memory configuration."""
    _validate_bundled_providers(config)
    update_config(config)
    return {"message": "Configuration set successfully"}
```

To:
```python
@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any], _admin=Depends(require_admin)):
    """Set memory configuration."""
    _validate_bundled_providers(config)
    update_config(config)
    return {"message": "Configuration set successfully"}
```

Update the import at the top of `server/main.py` (line 16) — add `require_admin`:

From:
```python
from auth import ADMIN_API_KEY, AUTH_DISABLED, JWT_SECRET, verify_auth
```

To:
```python
from auth import ADMIN_API_KEY, AUTH_DISABLED, JWT_SECRET, require_admin, verify_auth
```

- [ ] **Step 4: Run the configure tests, confirm all pass**

Run: `cd server && pytest tests/test_admin_gating.py -k "configure" -v`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/tests/test_admin_gating.py
git commit -m "feat(server): admin-gate GET/POST /configure"
```

---

## Task 4: Admin-gate `POST /reset`

**Files:**
- Modify: `server/main.py:475-482`
- Modify: `server/tests/test_admin_gating.py` (append)

- [ ] **Step 1: Append failing tests for `/reset`**

Append to `server/tests/test_admin_gating.py`:

```python


# --- POST /reset ---


def test_post_reset_admin_jwt(client, auth_admin_header):
    response = client.post("/reset", headers=auth_admin_header)
    assert response.status_code == 200


def test_post_reset_admin_api_key(client, admin_api_key_env):
    response = client.post("/reset", headers=admin_api_key_env)
    assert response.status_code == 200


def test_post_reset_auth_disabled(client, auth_disabled_env):
    response = client.post("/reset")
    assert response.status_code == 200


def test_post_reset_member_forbidden(client, auth_member_header):
    response = client.post("/reset", headers=auth_member_header)
    assert response.status_code == 403


def test_post_reset_no_auth_unauthorized(client):
    response = client.post("/reset")
    assert response.status_code == 401
```

- [ ] **Step 2: Run, confirm member test FAILS**

Run: `cd server && pytest tests/test_admin_gating.py::test_post_reset_member_forbidden -v`
Expected: FAIL with `assert 200 == 403`.

- [ ] **Step 3: Swap the dep on `POST /reset`**

Edit `server/main.py`. Change lines 475-482:

From:
```python
@app.post("/reset", summary="Reset all memories")
def reset_memory(_auth=Depends(verify_auth)):
    """Completely reset stored memories."""
    try:
        get_memory_instance().reset()
        return {"message": "All memories reset"}
    except Exception:
        raise upstream_error()
```

To:
```python
@app.post("/reset", summary="Reset all memories")
def reset_memory(_admin=Depends(require_admin)):
    """Completely reset stored memories."""
    try:
        get_memory_instance().reset()
        return {"message": "All memories reset"}
    except Exception:
        raise upstream_error()
```

- [ ] **Step 4: Run, confirm all pass**

Run: `cd server && pytest tests/test_admin_gating.py -k "reset" -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add server/main.py server/tests/test_admin_gating.py
git commit -m "feat(server): admin-gate POST /reset"
```

---

## Task 5: Admin-gate `GET /entities` and `DELETE /entities/{type}/{id}`

**Files:**
- Modify: `server/routers/entities.py`
- Modify: `server/tests/test_admin_gating.py` (append)

- [ ] **Step 1: Append failing tests for `/entities`**

Append to `server/tests/test_admin_gating.py`:

```python


# --- GET /entities ---


def test_get_entities_admin_jwt(client, auth_admin_header):
    response = client.get("/entities", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_entities_admin_api_key(client, admin_api_key_env):
    response = client.get("/entities", headers=admin_api_key_env)
    assert response.status_code == 200


def test_get_entities_auth_disabled(client, auth_disabled_env):
    response = client.get("/entities")
    assert response.status_code == 200


def test_get_entities_member_forbidden(client, auth_member_header):
    response = client.get("/entities", headers=auth_member_header)
    assert response.status_code == 403


def test_get_entities_no_auth_unauthorized(client):
    response = client.get("/entities")
    assert response.status_code == 401


# --- DELETE /entities/{type}/{id} ---


def test_delete_entity_admin_jwt(client, auth_admin_header):
    response = client.delete("/entities/user/alice", headers=auth_admin_header)
    assert response.status_code == 200


def test_delete_entity_admin_api_key(client, admin_api_key_env):
    response = client.delete("/entities/user/alice", headers=admin_api_key_env)
    assert response.status_code == 200


def test_delete_entity_auth_disabled(client, auth_disabled_env):
    response = client.delete("/entities/user/alice")
    assert response.status_code == 200


def test_delete_entity_member_forbidden(client, auth_member_header):
    response = client.delete("/entities/user/alice", headers=auth_member_header)
    assert response.status_code == 403


def test_delete_entity_no_auth_unauthorized(client):
    response = client.delete("/entities/user/alice")
    assert response.status_code == 401
```

- [ ] **Step 2: Run, confirm member tests FAIL**

Run: `cd server && pytest tests/test_admin_gating.py -k "entities" -v`
Expected: 2 failures on the `_member_forbidden` tests.

- [ ] **Step 3: Swap the deps on both entity routes**

Edit `server/routers/entities.py`.

Change the imports (line 8):

From:
```python
from auth import verify_auth
```

To:
```python
from auth import require_admin
```

Change lines 44-45:

From:
```python
@router.get("", response_model=list[Entity])
def list_entities(_auth=Depends(verify_auth)):
```

To:
```python
@router.get("", response_model=list[Entity])
def list_entities(_admin=Depends(require_admin)):
```

Change lines 71-72:

From:
```python
@router.delete("/{entity_type}/{entity_id}", response_model=MessageResponse)
def delete_entity(entity_type: EntityType, entity_id: str, _auth=Depends(verify_auth)):
```

To:
```python
@router.delete("/{entity_type}/{entity_id}", response_model=MessageResponse)
def delete_entity(entity_type: EntityType, entity_id: str, _admin=Depends(require_admin)):
```

- [ ] **Step 4: Run, confirm all entity tests pass**

Run: `cd server && pytest tests/test_admin_gating.py -k "entities or entity" -v`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add server/routers/entities.py server/tests/test_admin_gating.py
git commit -m "feat(server): admin-gate GET /entities and DELETE /entities/{type}/{id}"
```

---

## Task 6: Admin-gate `GET /requests`

**Files:**
- Modify: `server/routers/requests.py`
- Modify: `server/tests/test_admin_gating.py` (append)

- [ ] **Step 1: Append failing tests for `/requests`**

Append to `server/tests/test_admin_gating.py`:

```python


# --- GET /requests ---


def test_get_requests_admin_jwt(client, auth_admin_header):
    response = client.get("/requests", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_requests_admin_api_key(client, admin_api_key_env):
    response = client.get("/requests", headers=admin_api_key_env)
    assert response.status_code == 200


def test_get_requests_auth_disabled(client, auth_disabled_env):
    response = client.get("/requests")
    assert response.status_code == 200


def test_get_requests_member_forbidden(client, auth_member_header):
    response = client.get("/requests", headers=auth_member_header)
    assert response.status_code == 403


def test_get_requests_no_auth_unauthorized(client):
    response = client.get("/requests")
    assert response.status_code == 401
```

- [ ] **Step 2: Run, confirm member test FAILS**

Run: `cd server && pytest tests/test_admin_gating.py -k "requests" -v`
Expected: 1 failure on `test_get_requests_member_forbidden` (currently passes auth via `require_auth`).

- [ ] **Step 3: Swap dep + drop unused `user` parameter**

Edit `server/routers/requests.py`.

Change the imports block:

From:
```python
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import RequestLog, User
```

To:
```python
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import require_admin
from db import get_db
from models import RequestLog
```

(Dropped `require_auth` and the now-unused `User` import.)

Change the route handler (lines 31-37):

From:
```python
@router.get("", response_model=list[RequestLogItem])
def list_requests(
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
```

To:
```python
@router.get("", response_model=list[RequestLogItem])
def list_requests(
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
```

- [ ] **Step 4: Run all admin-gating tests, confirm all pass**

Run: `cd server && pytest tests/test_admin_gating.py -v`
Expected: `30 passed` (5 routes × 5 cases each = 25, plus 5 from delete_entity = 30).

- [ ] **Step 5: Commit**

```bash
git add server/routers/requests.py server/tests/test_admin_gating.py
git commit -m "feat(server): admin-gate GET /requests"
```

---

## Task 7: Inside-route guard on `GET /memories` (no-filter branch)

**Files:**
- Modify: `server/main.py:387-403`
- Modify: `server/tests/test_admin_gating.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `server/tests/test_admin_gating.py`:

```python


# --- GET /memories (no filter branch only) ---


def test_get_memories_no_filter_admin_jwt(client, auth_admin_header):
    response = client.get("/memories", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_memories_no_filter_admin_api_key(client, admin_api_key_env):
    response = client.get("/memories", headers=admin_api_key_env)
    assert response.status_code == 200


def test_get_memories_no_filter_auth_disabled(client, auth_disabled_env):
    response = client.get("/memories")
    assert response.status_code == 200


def test_get_memories_no_filter_member_forbidden(client, auth_member_header):
    """The info-disclosure branch (_list_all_memories) is admin-only."""
    response = client.get("/memories", headers=auth_member_header)
    assert response.status_code == 403


def test_get_memories_filtered_member_succeeds(client, auth_member_header):
    """Filtered queries are unchanged — member can still call them."""
    response = client.get("/memories?user_id=alice", headers=auth_member_header)
    assert response.status_code == 200


def test_get_memories_no_auth_unauthorized(client):
    response = client.get("/memories")
    assert response.status_code == 401
```

- [ ] **Step 2: Run, confirm member-no-filter FAILS**

Run: `cd server && pytest tests/test_admin_gating.py -k "memories_no_filter_member" -v`
Expected: FAIL with `assert 200 == 403`.

- [ ] **Step 3: Refactor `GET /memories` to use the inside-route guard**

Edit `server/main.py`.

Update the import at line 16 to also pull `_ensure_admin`:

From:
```python
from auth import ADMIN_API_KEY, AUTH_DISABLED, JWT_SECRET, require_admin, verify_auth
```

To:
```python
from auth import ADMIN_API_KEY, AUTH_DISABLED, JWT_SECRET, _ensure_admin, require_admin, verify_auth
```

Replace the `GET /memories` handler (lines 387-403). From:

```python
@app.get("/memories", summary="Get memories")
def get_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    _auth=Depends(verify_auth),
):
    """Retrieve stored memories. Lists all memories when no identifier is provided."""
    try:
        if not any([user_id, run_id, agent_id]):
            return _list_all_memories()
        filters = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        return get_memory_instance().get_all(filters=filters)
    except Exception:
        raise upstream_error()
```

To:

```python
@app.get("/memories", summary="Get memories")
def get_all_memories(
    request: Request,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    user: User | None = Depends(verify_auth),
):
    """Retrieve stored memories. Lists all memories when no identifier is provided.

    Note: the unfiltered listing branch is admin-only — it would otherwise leak
    every payload in the vector store across tenants once multi-user lands.
    Filtered queries remain available to any authenticated caller."""
    try:
        if not any([user_id, run_id, agent_id]):
            _ensure_admin(request, user)
            return _list_all_memories()
        filters = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        return get_memory_instance().get_all(filters=filters)
    except HTTPException:
        raise
    except Exception:
        raise upstream_error()
```

Two changes worth flagging:
- The signature now takes `request: Request` and renames `_auth` → `user` so the guard can read it.
- The `try` block now re-raises `HTTPException` before falling through to `upstream_error()`. Without this, the 403 we just added would get swallowed and turned into a generic 502/500.

Also add `User` to the imports if it's not already there. Check `server/main.py:31` — it imports `RequestLog, User` from `models`, so we're covered.

- [ ] **Step 4: Run, confirm all `/memories` tests pass**

Run: `cd server && pytest tests/test_admin_gating.py -k "memories" -v`
Expected: `6 passed`.

- [ ] **Step 5: Run the full admin-gating suite to confirm no regression**

Run: `cd server && pytest tests/test_admin_gating.py -v`
Expected: `36 passed`.

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/tests/test_admin_gating.py
git commit -m "feat(server): admin-gate unfiltered GET /memories branch"
```

---

## Task 8: Regression tests for unchanged routes

**Files:**
- Create: `server/tests/test_unchanged_routes.py`

These tests assert that the routes we *deliberately* left alone still behave correctly for admins (the only user type that exists today). They lock the behavior in place so future refactors can't silently change it.

- [ ] **Step 1: Write the regression tests**

Write `server/tests/test_unchanged_routes.py`:

```python
"""Regression tests for routes deliberately left untouched by the authz fix.

These prove the per-route changes did not accidentally regress memory CRUD,
search, or the API-key management endpoints."""

from __future__ import annotations


def test_post_memories_admin_succeeds(client, auth_admin_header):
    response = client.post(
        "/memories",
        headers=auth_admin_header,
        json={
            "messages": [{"role": "user", "content": "I love pizza."}],
            "user_id": "alice",
        },
    )
    assert response.status_code == 200


def test_post_memories_requires_identifier(client, auth_admin_header):
    response = client.post(
        "/memories",
        headers=auth_admin_header,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400


def test_get_memories_filtered_admin_succeeds(client, auth_admin_header):
    response = client.get("/memories?user_id=alice", headers=auth_admin_header)
    assert response.status_code == 200


def test_post_search_admin_succeeds(client, auth_admin_header):
    response = client.post(
        "/search",
        headers=auth_admin_header,
        json={"query": "pizza", "user_id": "alice"},
    )
    assert response.status_code == 200


def test_get_memory_by_id_admin_succeeds(client, auth_admin_header):
    response = client.get("/memories/some-id", headers=auth_admin_header)
    assert response.status_code == 200


def test_delete_memories_filtered_admin_succeeds(client, auth_admin_header):
    response = client.delete("/memories?user_id=alice", headers=auth_admin_header)
    assert response.status_code == 200


def test_delete_memories_no_filter_returns_400(client, auth_admin_header):
    """Even admin must supply an identifier for filtered delete."""
    response = client.delete("/memories", headers=auth_admin_header)
    assert response.status_code == 400


def test_get_configure_providers_admin_succeeds(client, auth_admin_header):
    """GET /configure/providers stays on verify_auth (not admin-gated)."""
    response = client.get("/configure/providers", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_configure_providers_member_succeeds(client, auth_member_header):
    """Members can still query bundled providers — not admin-gated."""
    response = client.get("/configure/providers", headers=auth_member_header)
    assert response.status_code == 200


def test_api_keys_list_admin_succeeds(client, auth_admin_header):
    response = client.get("/api-keys", headers=auth_admin_header)
    assert response.status_code == 200


def test_api_keys_list_member_succeeds(client, auth_member_header):
    """API-key management remains scoped to the caller (require_auth, not require_admin)."""
    response = client.get("/api-keys", headers=auth_member_header)
    assert response.status_code == 200


def test_auth_me_admin_succeeds(client, auth_admin_header):
    response = client.get("/auth/me", headers=auth_admin_header)
    assert response.status_code == 200


def test_setup_status_no_auth(client):
    """Open route — no auth required even after the fix."""
    response = client.get("/auth/setup-status")
    assert response.status_code == 200
```

- [ ] **Step 2: Run the regression suite**

Run: `cd server && pytest tests/test_unchanged_routes.py -v`
Expected: `13 passed`.

- [ ] **Step 3: Run the full server test suite to confirm everything is green**

Run: `cd server && pytest tests/ -v`
Expected: `55 passed` (6 helpers + 36 admin-gating + 13 unchanged).

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_unchanged_routes.py
git commit -m "test(server): regression coverage for routes untouched by authz fix"
```

---

## Task 9: Docs — surgical edits to `rest-api.mdx`

**Files:**
- Modify: `docs/open-source/features/rest-api.mdx`

- [ ] **Step 1: Update the auth-table row for per-user API keys (line 134)**

Find this line (in the auth-modes table around lines 131-136):

```markdown
| Per-user API key | `X-API-Key: m0sk_...` | Programmatic access scoped to a single dashboard user |
```

Replace with:

```markdown
| Per-user API key | `X-API-Key: m0sk_...` | Programmatic access tied to the single admin user today. Per-user scoping arrives with the upcoming multi-user invite flow |
```

- [ ] **Step 2: Remove the inaccurate "inherit scope" sentence (line 185)**

Find this line:

```markdown
Per-user keys inherit the creating user's scope. List or revoke them via `GET /api-keys` and `DELETE /api-keys/{id}`.
```

Replace with:

```markdown
List or revoke per-user keys via `GET /api-keys` and `DELETE /api-keys/{id}`. The dashboard user issued the key remains its owner; admin-only routes such as `/configure`, `/reset`, `/entities`, and `/requests` require the issuing user to have the admin role.
```

- [ ] **Step 3: Annotate admin-only endpoints in the reference tables**

In the "Memory operations" table (around lines 247-260), change:

```markdown
| `POST` | `/configure` | Set memory configuration. Rejects unbundled providers with a 400 |
| `GET` | `/configure` | Get the current memory configuration |
```

To:

```markdown
| `POST` | `/configure` | **Admin only.** Set memory configuration. Rejects unbundled providers with a 400 |
| `GET` | `/configure` | **Admin only.** Get the current memory configuration |
```

And:

```markdown
| `POST` | `/reset` | Reset all memories |
```

To:

```markdown
| `POST` | `/reset` | **Admin only.** Reset all memories |
```

In the "Entities" table (around lines 290-296), change:

```markdown
| `GET` | `/entities` | Distinct `user_id` / `agent_id` / `run_id` values with memory counts |
| `DELETE` | `/entities/{entity_type}/{entity_id}` | Cascade-delete all memories for an entity; `entity_type` is `user`, `agent`, or `run` |
```

To:

```markdown
| `GET` | `/entities` | **Admin only.** Distinct `user_id` / `agent_id` / `run_id` values with memory counts |
| `DELETE` | `/entities/{entity_type}/{entity_id}` | **Admin only.** Cascade-delete all memories for an entity; `entity_type` is `user`, `agent`, or `run` |
```

In the "Request logs" table:

```markdown
| `GET` | `/requests?limit=N` | Recent API call log (JWT or admin key) |
```

To:

```markdown
| `GET` | `/requests?limit=N` | **Admin only.** Recent API call log |
```

- [ ] **Step 4: Add a "coming soon" marker to the multi-user promise (line ~267)**

Find this line in the auth-endpoints section:

```markdown
| `POST` | `/auth/register` | Register the first admin. Registration closes after the first admin is created; additional accounts are provisioned by the existing admin. |
```

Replace with:

```markdown
| `POST` | `/auth/register` | Register the first admin. Registration closes after the first admin is created; additional accounts will be provisioned by the existing admin (multi-user invite flow coming soon). |
```

- [ ] **Step 5: Verify `docs/llms.txt` is still in sync**

Run: `python scripts/check-llms-txt-coverage.py`
Expected: exit 0 (no changes — we did not add or remove any `.mdx` pages, just edited an existing one).

- [ ] **Step 6: Commit**

```bash
git add docs/open-source/features/rest-api.mdx
git commit -m "docs(rest-api): document admin-only routes and clarify per-user-key scope"
```

---

## Task 10: CI workflow for `server/`

**Files:**
- Create: `.github/workflows/server-ci.yml`

- [ ] **Step 1: Create the workflow file**

Write `.github/workflows/server-ci.yml`:

```yaml
name: Server CI

on:
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - 'server/**'
      - '.github/workflows/server-ci.yml'
  pull_request:
    paths:
      - 'server/**'
      - '.github/workflows/server-ci.yml'

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dev dependencies
        working-directory: server
        run: pip install -r requirements-dev.txt

      - name: Run tests
        working-directory: server
        env:
          JWT_SECRET: ci-test-secret-do-not-use-in-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
          OPENAI_API_KEY: ci-test-key
        run: pytest tests/ -v
```

- [ ] **Step 2: Verify locally that the workflow would pass**

Run: `cd server && JWT_SECRET=ci-test-secret-do-not-use-in-prod-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx OPENAI_API_KEY=ci-test-key pytest tests/ -v`
Expected: `55 passed`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/server-ci.yml
git commit -m "ci(server): add pytest workflow on PRs touching server/"
```

---

## Task 11: Final verification + PR draft

- [ ] **Step 1: Run the full test suite one more time**

Run: `cd server && pytest tests/ -v`
Expected: `55 passed, 0 failed`.

- [ ] **Step 2: Review the diff**

Run: `git log --oneline main..HEAD` and `git diff main --stat`
Expected: ~10 commits, modifications confined to `server/`, `docs/open-source/features/rest-api.mdx`, `docs/superpowers/`, and `.github/workflows/server-ci.yml`. Roughly 30 LOC of production code change, the rest is tests, docs, and CI.

- [ ] **Step 3: Draft the PR description**

Use this template:

```markdown
## Linked Issue

Closes <fill in> — security report from vonbrubeck@gmail.com (2026-05-01) on REST API per-user API key authorization.

## Description

Hardens the self-hosted OSS REST server's authorization model by admin-gating
six global / destructive / info-disclosing routes and adding an inside-route
guard on `GET /memories`. Also adds the first `server/tests/` pytest scaffold
so this change (and future ones) have automated regression coverage.

Scope: B+ from `docs/superpowers/specs/2026-05-13-rest-api-authz-fix-design.md`.
Deferred to follow-up issue:
- `owner_id` on memory payloads
- Multi-user invite/provision flow
- Rate-limiting `/generate-instructions`
- Per-owner filtering on `/requests`

Zero behavior change on every supported deployment mode today (single-admin
JWT, single-admin per-user API key, legacy `ADMIN_API_KEY` env,
`AUTH_DISABLED=true`).

## Type of Change

- [x] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature
- [ ] Breaking change
- [ ] Refactor
- [x] Documentation update

## Breaking Changes

None. The new 403 path is reachable only by a non-admin `User`, which the
current schema (partial unique index in migration 004, closed `/auth/register`)
cannot produce via public APIs.

## Test Coverage

- [x] Added unit tests for `_ensure_admin`
- [x] Added integration tests for the 6 admin-gated routes + `GET /memories` inside-route guard
- [x] Added regression tests for routes deliberately left unchanged
- [x] Tested manually: `ADMIN_API_KEY` env, `AUTH_DISABLED=true`, admin JWT, admin per-user key

## Checklist

- [x] Code follows the project's style guidelines
- [x] Self-review performed
- [x] New tests prove the fix works
- [x] All tests pass locally
- [x] Documentation updated
```

- [ ] **Step 4: Open the PR**

```bash
git push -u origin <current-branch>
gh pr create --title "fix(server): admin-gate global REST routes; fix docs/code authz mismatch" \
  --body-file <(cat <<'EOF'
[paste PR body from Step 3]
EOF
)
```

- [ ] **Step 5: After PR opens, file the follow-up issue**

Body of the follow-up GitHub issue (single body, no separate design doc):

```markdown
## Follow-up: REST API multi-user authorization (owner_id + invite flow)

Tracked from #<this-PR> per `docs/superpowers/specs/2026-05-13-rest-api-authz-fix-design.md`.

The B+ fix in #<this-PR> admin-gates the global/destructive routes but does not
add per-user scoping to the memory CRUD routes. That requires:

### 1. `owner_id` on memory payloads
Decide whether to store `owner_id` as a JSONB payload key or as a first-class
column on the vector-store row. Spec the backfill story for existing
deployments (assign all existing rows to the single admin). Wire the write
path (`POST /memories`) to inject `owner_id` from the authenticated `User`,
and every read path (`GET /memories` filtered, `POST /search`, all
`memory_id` ops) to filter or check ownership.

### 2. Multi-user invite flow
The docs at `rest-api.mdx` already promise this. Spec the UX: roles
(admin/member/viewer?), per-org structure, invite endpoint, accept flow,
role transitions.

### 3. Rate-limit `POST /generate-instructions`
Burns LLM tokens charged to the server's `OPENAI_API_KEY`. Adding a limit
could regress existing batch callers — gather usage data first, then decide.

### 4. Per-owner filtering on `GET /requests`
Requires `owner_id` on the `RequestLog` table (DB migration).
```

---

## Self-Review

Checking the plan against the spec:

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| `_ensure_admin` helper + `require_admin` dep | Task 2 |
| Full gate on `/configure` (GET + POST) | Task 3 |
| Full gate on `/reset` | Task 4 |
| Full gate on `/entities` (GET + DELETE) | Task 5 |
| Full gate on `/requests` | Task 6 |
| Inside-route guard on `GET /memories` | Task 7 |
| Routes deliberately NOT changed | Task 8 (regression coverage) |
| Docs surgical edits | Task 9 |
| Test scaffolding (`server/tests/`) | Tasks 1, 2, 3-8 |
| CI workflow | Task 10 |
| Regression matrix coverage (5 modes) | Built into every gating test |
| Acceptance criterion: ADMIN_API_KEY / AUTH_DISABLED automated coverage | Tasks 3-7 each include both |
| Follow-up issue body | Task 11, Step 5 |

**Type and method consistency:**

- `_ensure_admin(request, user)` signature is consistent in `server/auth.py`, the unit tests in Task 2, and the inside-route call site in Task 7.
- `require_admin` is called via `_admin=Depends(require_admin)` in every modified route (Tasks 3-6).
- Test fixtures (`admin_user`, `member_user`, `auth_admin_header`, `auth_member_header`, `admin_api_key_env`, `auth_disabled_env`) are defined in `conftest.py` (Task 1) and reused unchanged in Tasks 2-8.
- `JWT_SECRET` and `OPENAI_API_KEY` env vars are set in conftest (Task 1) and again in the CI workflow (Task 10) — same names.

**Placeholder scan:** none. Every step contains either a complete code block, an exact command, or a precise instruction with a from→to diff.

**KISS / DRY / minimal-changes audit:**

- Single helper (`_ensure_admin`) reused by both the FastAPI dep and the inline route guard — DRY.
- Six dep swaps are mechanically identical — one pattern, six call sites — KISS.
- No new infrastructure beyond what the spec required (no Postgres for tests, no separate design doc for the follow-up).
- `GET /configure/providers` deliberately not admin-gated, per the trim agreed during brainstorming.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-rest-api-authz-fix-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
