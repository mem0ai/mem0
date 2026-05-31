"""Comprehensive E2E tests for REST API server authentication.

Tests the actual server/main.py app through FastAPI's TestClient (full ASGI
round-trip) covering:
  - Auth disabled mode (ADMIN_API_KEY unset)
  - Auth enabled mode (ADMIN_API_KEY set)
  - Edge cases: empty keys, near-miss keys, timing-safe comparison, header
    casing, response headers, startup logging, and full CRUD flows through auth.
"""

import importlib
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _mock_memory():
    """Patch Memory.from_config so the server imports without a real backend."""
    mock_instance = MagicMock()
    # Set up return values so CRUD endpoints return realistic responses
    mock_instance.get.return_value = {"id": "mem-1", "memory": "test memory", "user_id": "alice"}
    mock_instance.get_all.return_value = [
        {"id": "mem-1", "memory": "test memory", "user_id": "alice"},
    ]
    mock_instance.add.return_value = {"results": [{"id": "mem-1", "event": "ADD", "memory": "test"}]}
    mock_instance.search.return_value = [{"id": "mem-1", "memory": "test", "score": 0.9}]
    mock_instance.update.return_value = {"message": "Memory updated"}
    mock_instance.history.return_value = [{"id": "mem-1", "old_memory": "a", "new_memory": "b"}]
    mock_instance.delete.return_value = None
    mock_instance.delete_all.return_value = {"message": "Memories deleted successfully!"}
    mock_instance.reset.return_value = None

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
        with patch("mem0.Memory.from_config", return_value=mock_instance):
            yield mock_instance


def _load_app(env_overrides: dict):
    """Reload server/main.py with the given environment and return the FastAPI app."""
    import server.main as server_main

    with patch.dict(os.environ, env_overrides, clear=False):
        importlib.reload(server_main)
    return server_main.app


# ---------------------------------------------------------------------------
# Auth disabled (ADMIN_API_KEY not set)
# ---------------------------------------------------------------------------

class TestAuthDisabled:
    """All endpoints should be freely accessible when ADMIN_API_KEY is empty."""

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_memory):
        self.app = _load_app({"ADMIN_API_KEY": ""})
        self.client = TestClient(self.app)
        self.mock = _mock_memory

    def test_root_redirects_to_docs(self):
        resp = self.client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert "/docs" in resp.headers["location"]

    def test_get_memory_without_key(self):
        resp = self.client.get("/memories/mem-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "mem-1"

    def test_get_all_memories_without_key(self):
        resp = self.client.get("/memories", params={"user_id": "alice"})
        assert resp.status_code == 200

    def test_create_memory_without_key(self):
        resp = self.client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "alice",
        })
        assert resp.status_code == 200

    def test_search_without_key(self):
        resp = self.client.post("/search", json={"query": "pizza", "user_id": "alice"})
        assert resp.status_code == 200

    def test_update_memory_without_key(self):
        resp = self.client.put("/memories/mem-1", json={"text": "updated"})
        assert resp.status_code == 200

    def test_history_without_key(self):
        resp = self.client.get("/memories/mem-1/history")
        assert resp.status_code == 200

    def test_delete_memory_without_key(self):
        resp = self.client.delete("/memories/mem-1")
        assert resp.status_code == 200

    def test_delete_all_without_key(self):
        resp = self.client.delete("/memories", params={"user_id": "alice"})
        assert resp.status_code == 200

    def test_reset_without_key(self):
        resp = self.client.post("/reset")
        assert resp.status_code == 200

    def test_configure_without_key(self):
        self.mock.from_config = MagicMock()
        resp = self.client.post("/configure", json={"version": "v1.1"})
        assert resp.status_code == 200

    def test_supplying_key_still_works_when_auth_disabled(self):
        """A client that sends X-API-Key should not be penalized when auth is off."""
        resp = self.client.get(
            "/memories/mem-1", headers={"X-API-Key": "some-random-key"}
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/configure"),
            ("POST", "/memories"),
            ("GET", "/memories"),
            ("GET", "/memories/test-id"),
            ("POST", "/search"),
            ("PUT", "/memories/test-id"),
            ("GET", "/memories/test-id/history"),
            ("DELETE", "/memories/test-id"),
            ("DELETE", "/memories"),
            ("POST", "/reset"),
        ],
    )
    def test_no_endpoint_returns_401_when_auth_disabled(self, method, path):
        resp = self.client.request(method, path)
        assert resp.status_code != 401, f"{method} {path} should not require auth"


# ---------------------------------------------------------------------------
# Auth enabled (ADMIN_API_KEY set)
# ---------------------------------------------------------------------------

class TestAuthEnabled:
    """All protected endpoints must enforce the API key."""

    API_KEY = "test-secret-key-12345"

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_memory):
        self.app = _load_app({"ADMIN_API_KEY": self.API_KEY})
        self.client = TestClient(self.app)
        self.mock = _mock_memory

    # --- Rejection cases ---

    def test_missing_key_returns_401(self):
        resp = self.client.get("/memories/mem-1")
        assert resp.status_code == 401

    def test_missing_key_detail_mentions_header(self):
        resp = self.client.get("/memories/mem-1")
        assert "X-API-Key" in resp.json()["detail"]

    def test_wrong_key_returns_401(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_wrong_key_detail_says_invalid(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": "wrong"})
        assert "Invalid" in resp.json()["detail"]

    def test_empty_string_key_returns_401(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": ""})
        assert resp.status_code == 401

    def test_401_includes_www_authenticate_header(self):
        resp = self.client.get("/memories/mem-1")
        assert resp.headers.get("www-authenticate") == "ApiKey"

    def test_near_miss_key_rejected(self):
        """Key that differs by one character should be rejected."""
        near_miss = self.API_KEY[:-1] + ("6" if self.API_KEY[-1] != "6" else "7")
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": near_miss})
        assert resp.status_code == 401

    def test_key_with_extra_whitespace_rejected(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": f" {self.API_KEY} "})
        assert resp.status_code == 401

    def test_key_prefix_rejected(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": self.API_KEY[:5]})
        assert resp.status_code == 401

    def test_key_with_different_case_rejected(self):
        resp = self.client.get("/memories/mem-1", headers={"X-API-Key": self.API_KEY.upper()})
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/configure"),
            ("POST", "/memories"),
            ("GET", "/memories"),
            ("GET", "/memories/test-id"),
            ("POST", "/search"),
            ("PUT", "/memories/test-id"),
            ("GET", "/memories/test-id/history"),
            ("DELETE", "/memories/test-id"),
            ("DELETE", "/memories"),
            ("POST", "/reset"),
        ],
    )
    def test_all_endpoints_reject_without_key(self, method, path):
        resp = self.client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} should require auth"

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/configure"),
            ("POST", "/memories"),
            ("GET", "/memories"),
            ("GET", "/memories/test-id"),
            ("POST", "/search"),
            ("PUT", "/memories/test-id"),
            ("GET", "/memories/test-id/history"),
            ("DELETE", "/memories/test-id"),
            ("DELETE", "/memories"),
            ("POST", "/reset"),
        ],
    )
    def test_all_endpoints_reject_wrong_key(self, method, path):
        resp = self.client.request(method, path, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401, f"{method} {path} should reject wrong key"

    # --- Acceptance cases ---

    def test_root_does_not_require_key(self):
        resp = self.client.get("/", follow_redirects=False)
        assert resp.status_code == 307

    def _authed(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-API-Key"] = self.API_KEY
        return self.client.request(method, path, headers=headers, **kwargs)

    def test_get_memory_with_key(self):
        resp = self._authed("GET", "/memories/mem-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "mem-1"

    def test_get_all_memories_with_key(self):
        resp = self._authed("GET", "/memories", params={"user_id": "alice"})
        assert resp.status_code == 200

    def test_create_memory_with_key(self):
        resp = self._authed("POST", "/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "alice",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_search_with_key(self):
        resp = self._authed("POST", "/search", json={"query": "pizza", "user_id": "alice"})
        assert resp.status_code == 200

    def test_update_memory_with_key(self):
        resp = self._authed("PUT", "/memories/mem-1", json={"text": "updated"})
        assert resp.status_code == 200

    def test_history_with_key(self):
        resp = self._authed("GET", "/memories/mem-1/history")
        assert resp.status_code == 200

    def test_delete_memory_with_key(self):
        resp = self._authed("DELETE", "/memories/mem-1")
        assert resp.status_code == 200

    def test_delete_all_with_key(self):
        resp = self._authed("DELETE", "/memories", params={"user_id": "alice"})
        assert resp.status_code == 200

    def test_reset_with_key(self):
        resp = self._authed("POST", "/reset")
        assert resp.status_code == 200

    def test_configure_with_key(self):
        resp = self._authed("POST", "/configure", json={"version": "v1.1"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Full CRUD flow through auth
# ---------------------------------------------------------------------------

class TestAuthenticatedCRUDFlow:
    """Verify a complete create → read → search → update → history → delete
    cycle works end-to-end through the auth layer."""

    API_KEY = "flow-test-key-99"

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_memory):
        self.app = _load_app({"ADMIN_API_KEY": self.API_KEY})
        self.client = TestClient(self.app)
        self.mock = _mock_memory

    def _authed(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["X-API-Key"] = self.API_KEY
        return self.client.request(method, path, headers=headers, **kwargs)

    def test_full_crud_cycle(self):
        # 1. Create
        resp = self._authed("POST", "/memories", json={
            "messages": [{"role": "user", "content": "I love fresh vegetable pizza"}],
            "user_id": "alice",
        })
        assert resp.status_code == 200
        self.mock.add.assert_called_once()

        # 2. Read single
        resp = self._authed("GET", "/memories/mem-1")
        assert resp.status_code == 200
        self.mock.get.assert_called_once_with("mem-1")

        # 3. Read all
        resp = self._authed("GET", "/memories", params={"user_id": "alice"})
        assert resp.status_code == 200
        self.mock.get_all.assert_called_once_with(user_id="alice")

        # 4. Search
        resp = self._authed("POST", "/search", json={"query": "pizza", "user_id": "alice"})
        assert resp.status_code == 200
        self.mock.search.assert_called_once()

        # 5. Update
        resp = self._authed("PUT", "/memories/mem-1", json={"text": "updated content"})
        assert resp.status_code == 200
        self.mock.update.assert_called_once()

        # 6. History
        resp = self._authed("GET", "/memories/mem-1/history")
        assert resp.status_code == 200
        self.mock.history.assert_called_once_with(memory_id="mem-1")

        # 7. Delete single
        resp = self._authed("DELETE", "/memories/mem-1")
        assert resp.status_code == 200
        self.mock.delete.assert_called_once_with(memory_id="mem-1")

        # 8. Delete all
        resp = self._authed("DELETE", "/memories", params={"user_id": "alice"})
        assert resp.status_code == 200
        self.mock.delete_all.assert_called_once()

    def test_crud_flow_blocked_without_auth(self):
        """Same flow should fail at every step without the key."""
        endpoints = [
            ("POST", "/memories", {"json": {
                "messages": [{"role": "user", "content": "test"}], "user_id": "alice"
            }}),
            ("GET", "/memories/mem-1", {}),
            ("GET", "/memories", {"params": {"user_id": "alice"}}),
            ("POST", "/search", {"json": {"query": "pizza", "user_id": "alice"}}),
            ("PUT", "/memories/mem-1", {"json": {"data": "x"}}),
            ("GET", "/memories/mem-1/history", {}),
            ("DELETE", "/memories/mem-1", {}),
            ("DELETE", "/memories", {"params": {"user_id": "alice"}}),
            ("POST", "/reset", {}),
        ]
        for method, path, kwargs in endpoints:
            resp = self.client.request(method, path, **kwargs)
            assert resp.status_code == 401, f"Unauthenticated {method} {path} should be 401"
            # Verify the mock was NOT called (auth blocked before reaching handler)
        self.mock.add.assert_not_called()
        self.mock.get.assert_not_called()
        self.mock.search.assert_not_called()
        self.mock.update.assert_not_called()
        self.mock.history.assert_not_called()
        self.mock.delete.assert_not_called()
        self.mock.delete_all.assert_not_called()
        self.mock.reset.assert_not_called()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestAuthEdgeCases:
    """Boundary conditions and unusual inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_memory):
        self.mock = _mock_memory

    def test_very_long_api_key(self):
        """Server should handle a very long key without crashing."""
        long_key = "k" * 4096
        app = _load_app({"ADMIN_API_KEY": long_key})
        client = TestClient(app)
        resp = client.get("/memories/mem-1", headers={"X-API-Key": long_key})
        assert resp.status_code == 200

    def test_special_characters_in_api_key(self):
        """Keys with special ASCII characters should work."""
        special_key = "sk-!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        app = _load_app({"ADMIN_API_KEY": special_key})
        client = TestClient(app)

        resp = client.get("/memories/mem-1", headers={"X-API-Key": special_key})
        assert resp.status_code == 200

        resp = client.get("/memories/mem-1", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_key_env_var_not_present_at_all(self):
        """When the env var is completely absent, auth should be disabled."""
        import server.main as server_main
        env = os.environ.copy()
        env.pop("ADMIN_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            importlib.reload(server_main)
        client = TestClient(server_main.app)
        resp = client.get("/memories/mem-1")
        assert resp.status_code != 401

    def test_switching_from_enabled_to_disabled(self):
        """Simulates a server restart with auth toggled off."""
        # First: auth enabled
        app1 = _load_app({"ADMIN_API_KEY": "secret"})
        c1 = TestClient(app1)
        assert c1.get("/memories/mem-1").status_code == 401

        # Then: auth disabled
        app2 = _load_app({"ADMIN_API_KEY": ""})
        c2 = TestClient(app2)
        assert c2.get("/memories/mem-1").status_code != 401

    def test_openapi_schema_accessible_without_key(self):
        """The /docs and /openapi.json endpoints should always be reachable."""
        app = _load_app({"ADMIN_API_KEY": "secret"})
        client = TestClient(app)

        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema

        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_schema_documents_auth(self):
        """The OpenAPI schema should mention authentication."""
        app = _load_app({"ADMIN_API_KEY": "secret"})
        client = TestClient(app)
        schema = client.get("/openapi.json").json()
        assert "Authentication" in schema.get("info", {}).get("description", "")


# ---------------------------------------------------------------------------
# Startup logging
# ---------------------------------------------------------------------------

class TestStartupLogging:
    """Verify the server emits the correct log messages at import time."""

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_memory):
        pass

    def test_warning_when_auth_disabled(self, caplog):
        with caplog.at_level(logging.WARNING):
            _load_app({"ADMIN_API_KEY": ""})
        assert any("UNSECURED" in r.message for r in caplog.records)

    def test_info_when_auth_enabled(self, caplog):
        with caplog.at_level(logging.INFO):
            _load_app({"ADMIN_API_KEY": "a-long-enough-secret-key"})
        assert any("authentication enabled" in r.message for r in caplog.records)

    def test_warning_when_key_too_short(self, caplog):
        with caplog.at_level(logging.WARNING):
            _load_app({"ADMIN_API_KEY": "short"})
        assert any("shorter than" in r.message for r in caplog.records)
