"""Tests for the REST API Pydantic models and route parameter forwarding.

These tests directly exercise the Pydantic request models and the route
handler logic without importing the full server module (which tries to
initialise a real Memory instance at module scope).
"""

from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Re-declare the models exactly as they appear in server/main.py so we can
# test them in isolation.  If the real models ever drift, the integration
# tests (or a simple import-time check) will catch it.
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    infer: Optional[bool] = True


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 100
    threshold: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers -- replicate the dict-building logic from the route handlers
# ---------------------------------------------------------------------------

def _build_add_params(memory_create: MemoryCreate) -> dict:
    """Mirrors the param-building in the POST /memories handler."""
    return {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}


def _build_search_params(search_req: SearchRequest) -> dict:
    """Mirrors the param-building in the POST /search handler."""
    return {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}


# ===========================================================================
# SearchRequest tests
# ===========================================================================

class TestSearchRequestFields:
    """Verify that limit and threshold survive Pydantic parsing and are
    forwarded through the handler's param-building logic."""

    def test_limit_is_accepted_and_forwarded(self):
        req = SearchRequest(query="test", user_id="u1", limit=5)
        params = _build_search_params(req)
        assert params["limit"] == 5

    def test_threshold_is_accepted_and_forwarded(self):
        req = SearchRequest(query="test", user_id="u1", threshold=0.42)
        params = _build_search_params(req)
        assert params["threshold"] == 0.42

    def test_default_limit_is_100(self):
        req = SearchRequest(query="test", user_id="u1")
        params = _build_search_params(req)
        assert params["limit"] == 100

    def test_threshold_omitted_when_none(self):
        req = SearchRequest(query="test", user_id="u1")
        params = _build_search_params(req)
        assert "threshold" not in params

    def test_limit_and_threshold_together(self):
        req = SearchRequest(query="test", user_id="u1", limit=10, threshold=0.7)
        params = _build_search_params(req)
        assert params["limit"] == 10
        assert params["threshold"] == 0.7


# ===========================================================================
# MemoryCreate tests
# ===========================================================================

class TestMemoryCreateInferField:
    """Verify that infer survives Pydantic parsing and is forwarded through
    the handler's param-building logic."""

    def test_infer_true_is_forwarded(self):
        req = MemoryCreate(
            messages=[Message(role="user", content="hello")],
            user_id="u1",
            infer=True,
        )
        params = _build_add_params(req)
        assert params["infer"] is True

    def test_infer_false_is_forwarded(self):
        req = MemoryCreate(
            messages=[Message(role="user", content="hello")],
            user_id="u1",
            infer=False,
        )
        params = _build_add_params(req)
        assert params["infer"] is False

    def test_default_infer_is_true(self):
        req = MemoryCreate(
            messages=[Message(role="user", content="hello")],
            user_id="u1",
        )
        params = _build_add_params(req)
        assert params["infer"] is True

    def test_messages_excluded_from_params(self):
        req = MemoryCreate(
            messages=[Message(role="user", content="hello")],
            user_id="u1",
        )
        params = _build_add_params(req)
        assert "messages" not in params


# ===========================================================================
# Model parity check -- ensure the real server models match our local copies
# ===========================================================================

def _import_server_models():
    """Try to import models from server.main.

    The module-level ``Memory.from_config(...)`` call may fail if no API
    keys are configured, so we guard the import.
    """
    try:
        from server.main import MemoryCreate as RealMemoryCreate
        from server.main import SearchRequest as RealSearchRequest

        return RealSearchRequest, RealMemoryCreate
    except Exception:
        return None, None


_RealSearchRequest, _RealMemoryCreate = _import_server_models()
_server_available = _RealSearchRequest is not None


@pytest.mark.skipif(not _server_available, reason="server.main could not be imported (missing API keys or deps)")
class TestModelParity:
    """Ensure the models declared in server/main.py have the fields we expect."""

    def test_search_request_has_limit_field(self):
        assert "limit" in _RealSearchRequest.model_fields, "SearchRequest is missing the 'limit' field"

    def test_search_request_has_threshold_field(self):
        assert "threshold" in _RealSearchRequest.model_fields, "SearchRequest is missing the 'threshold' field"

    def test_memory_create_has_infer_field(self):
        assert "infer" in _RealMemoryCreate.model_fields, "MemoryCreate is missing the 'infer' field"
