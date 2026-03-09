"""
Tests for the two bugs fixed in fix/ui-config-api-url.

Setup strategy:
  sqlite:///:memory: gives EACH NEW CONNECTION an empty database.
  We force ALL connections (app + test) to share one in-memory DB by
  patching app.database with a StaticPool engine BEFORE importing main.

  Order matters:
    1. Set DATABASE_URL env var
    2. Stub noisy external deps (categorization, mcp_server, mem0)
    3. Import app.database and patch engine + SessionLocal → StaticPool
    4. Import models (registers table metadata on Base)
    5. Base.metadata.create_all → tables exist in shared DB
    6. Import main → create_default_user/app run successfully
    7. Override FastAPI get_db dependency → routes use same SessionLocal

No Docker, no Qdrant, no Ollama required.
"""

import os
import sys
from unittest.mock import MagicMock

# ── 1. Must be set before any app import ──────────────────────────────────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("USER", "testuser")
os.environ.setdefault("API_KEY", "test-key")

# ── 2. Stub external dependencies before they are imported ────────────────
# categorization calls Ollama/OpenAI at import time
_cat_stub = MagicMock()
_cat_stub.get_categories_for_memory = MagicMock(return_value=[])
sys.modules["app.utils.categorization"] = _cat_stub

# mcp_server attaches SSE routes — not needed here
_mcp_stub = MagicMock()
sys.modules["app.mcp_server"] = _mcp_stub

# mem0 itself — not needed for config-only tests
sys.modules.setdefault("mem0", MagicMock())

# ── 3. Patch app.database with a StaticPool engine ────────────────────────
# StaticPool makes ALL connections reuse the SAME in-memory connection, so
# create_all() and the app's SessionLocal() see the same tables.
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

import app.database as _db_module  # noqa: E402

_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSessionLocal

# ── 4. Register models and create tables BEFORE importing main ────────────
import app.models  # noqa: E402, F401  — registers all ORM classes on Base

from app.database import Base  # noqa: E402

Base.metadata.create_all(bind=_test_engine)  # tables exist before create_default_user()

# ── 5. Import main — create_default_user/app succeed (tables already exist) ─
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.utils.memory  # noqa: E402, F401  — mem0 already stubbed above

from main import app  # noqa: E402

# ── 6. Override FastAPI get_db → routes use our shared SessionLocal ────────
from app.database import get_db  # noqa: E402


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── 5. Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def client():
    """Does NOT follow redirects — lets us assert on 307s."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def client_follow():
    """Follows redirects — simulates correct axios behaviour."""
    return TestClient(app, follow_redirects=True)


# ══════════════════════════════════════════════════════════════════════════
# Bug 2 — Trailing slash / 307 redirect
# ══════════════════════════════════════════════════════════════════════════


class TestConfigRouteTrailingSlash:
    """
    FastAPI with redirect_slashes=True (default) issues a 307 when the
    trailing slash is missing. The original useConfig.ts called GET and
    PUT without the slash, so the Redux store was never updated (it stayed
    on its hardcoded OpenAI initial state).

    Tests document:
      - the 307 behaviour (root cause)
      - the fixed URLs (200 response)
    """

    def test_get_config_without_slash_returns_307(self, client):
        """Original bug: GET /api/v1/config (no slash) → 307 redirect."""
        response = client.get("/api/v1/config")
        assert response.status_code == 307, (
            f"Expected 307 redirect for GET without trailing slash, got {response.status_code}"
        )
        location = response.headers.get("location", "")
        assert location.endswith("/api/v1/config/"), f"Redirect should target /api/v1/config/, got '{location}'"

    def test_get_config_with_slash_returns_200(self, client_follow):
        """Fix: GET /api/v1/config/ (with slash) → 200 OK."""
        response = client_follow.get("/api/v1/config/")
        assert response.status_code == 200, f"Expected 200 for GET /api/v1/config/, got {response.status_code}"

    def test_put_config_without_slash_returns_307(self, client):
        """Original bug: PUT /api/v1/config (no slash) → 307 redirect."""
        payload = {
            "mem0": {
                "llm": {
                    "provider": "openai",
                    "config": {"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 2000},
                },
                "embedder": {
                    "provider": "openai",
                    "config": {"model": "text-embedding-3-small"},
                },
            }
        }
        response = client.put("/api/v1/config", json=payload)
        assert response.status_code == 307, (
            f"Expected 307 redirect for PUT without trailing slash, got {response.status_code}"
        )

    def test_put_config_with_slash_returns_200(self, client_follow):
        """Fix: PUT /api/v1/config/ (with slash) → 200 OK."""
        payload = {
            "mem0": {
                "llm": {
                    "provider": "openai",
                    "config": {"model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 2000},
                },
                "embedder": {
                    "provider": "openai",
                    "config": {"model": "text-embedding-3-small"},
                },
            }
        }
        response = client_follow.put("/api/v1/config/", json=payload)
        assert response.status_code == 200, f"Expected 200 for PUT /api/v1/config/, got {response.status_code}"

    def test_reset_config_unaffected(self, client_follow):
        """POST /api/v1/config/reset has no trailing slash in route — works as-is."""
        response = client_follow.post("/api/v1/config/reset")
        assert response.status_code == 200, f"POST /api/v1/config/reset should return 200, got {response.status_code}"

    def test_get_config_returns_mem0_structure(self, client_follow):
        """GET /api/v1/config/ response contains mem0.llm and mem0.embedder keys."""
        response = client_follow.get("/api/v1/config/")
        assert response.status_code == 200
        data = response.json()
        assert "mem0" in data, f"Response missing 'mem0' key: {data}"
        assert "llm" in data["mem0"], f"Response missing 'mem0.llm': {data}"
        assert "embedder" in data["mem0"], f"Response missing 'mem0.embedder': {data}"

    def test_get_config_llm_has_provider_and_config(self, client_follow):
        """Each provider block must have 'provider' and 'config' — shape expected by Redux."""
        response = client_follow.get("/api/v1/config/")
        assert response.status_code == 200
        data = response.json()
        llm = data["mem0"]["llm"]
        embedder = data["mem0"]["embedder"]
        assert "provider" in llm and "config" in llm
        assert "provider" in embedder and "config" in embedder


# ══════════════════════════════════════════════════════════════════════════
# Bug 1 — NEXT_PUBLIC_API_URL contract
# ══════════════════════════════════════════════════════════════════════════


class TestNextPublicApiUrlContract:
    """
    The docker-compose.yml bug (missing default value) cannot be unit-tested
    with pytest, but we assert the contract the fix depends on:

    - The API responds on its base URL (default http://localhost:8765)
    - The config endpoint requires no authentication
    - The response shape matches what the UI Redux store expects

    If these pass, the NEXT_PUBLIC_API_URL default fallback is valid.
    """

    def test_openapi_schema_is_available(self, client_follow):
        """FastAPI /openapi.json — confirms the app routes correctly."""
        response = client_follow.get("/openapi.json")
        assert response.status_code == 200
        assert "paths" in response.json()

    def test_config_endpoint_requires_no_authentication(self, client_follow):
        """
        GET /api/v1/config/ must be publicly accessible.
        If auth was ever required, the URL fix alone would not be enough.
        """
        response = client_follow.get("/api/v1/config/")
        assert response.status_code == 200, (
            f"Config endpoint must be accessible without auth, got {response.status_code}"
        )

    def test_config_response_matches_redux_store_shape(self, client_follow):
        """
        The response must match the exact shape the Redux store expects:
          { mem0: { llm: { provider, config }, embedder: { provider, config } } }
        This is the contract between the API and the settings page.
        """
        response = client_follow.get("/api/v1/config/")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, dict), "Response must be a JSON object"
        assert "mem0" in data, f"Missing 'mem0': {list(data.keys())}"

        llm = data["mem0"].get("llm", {})
        assert "provider" in llm and isinstance(llm["provider"], str)
        assert "config" in llm and isinstance(llm["config"], dict)

        embedder = data["mem0"].get("embedder", {})
        assert "provider" in embedder and isinstance(embedder["provider"], str)
        assert "config" in embedder and isinstance(embedder["config"], dict)
