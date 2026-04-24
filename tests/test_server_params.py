"""Tests for REST API parameter forwarding.

Verifies that the Pydantic request models in server/main.py correctly accept
and forward all parameters supported by the underlying Memory class methods,
including top_k, threshold, infer, memory_type, and prompt — which were
previously silently dropped by Pydantic v2's default extra='ignore' behavior.
"""

import importlib
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
    mock_instance.add.return_value = {"results": [{"id": "mem-1", "event": "ADD", "memory": "test"}]}
    mock_instance.search.return_value = [{"id": "mem-1", "memory": "test", "score": 0.9}]
    mock_instance.get.return_value = {"id": "mem-1", "memory": "test memory"}
    mock_instance.get_all.return_value = [{"id": "mem-1", "memory": "test memory"}]
    mock_instance.update.return_value = {"message": "Memory updated"}
    mock_instance.history.return_value = [{"id": "mem-1", "old_memory": "a", "new_memory": "b"}]
    mock_instance.delete.return_value = None
    mock_instance.delete_all.return_value = {"message": "Memories deleted"}
    mock_instance.reset.return_value = None

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": ""}):
        with patch("mem0.Memory.from_config", return_value=mock_instance):
            yield mock_instance


@pytest.fixture
def client(_mock_memory):
    """Return a TestClient wired to the server app with mocked Memory."""
    import server.main as server_main
    with patch.dict(os.environ, {"ADMIN_API_KEY": ""}):
        importlib.reload(server_main)
    return TestClient(server_main.app)


@pytest.fixture
def mock_memory(_mock_memory):
    return _mock_memory


# ===========================================================================
# SearchRequest: top_k parameter
# ===========================================================================

class TestSearchLimit:
    """Verify that the top_k parameter is accepted and forwarded to Memory.search()."""

    def test_limit_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "top_k": 5})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["top_k"] == 5

    def test_limit_one(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "top_k": 1})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["top_k"] == 1

    def test_limit_omitted_uses_memory_default(self, client, mock_memory):
        """When top_k is not sent, it should not appear in the kwargs,
        allowing Memory.search() to use its own default (100)."""
        resp = client.post("/search", json={"query": "food", "user_id": "u1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "top_k" not in kwargs


# ===========================================================================
# SearchRequest: threshold parameter
# ===========================================================================

class TestSearchThreshold:
    """Verify that the threshold parameter is accepted and forwarded."""

    def test_threshold_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "threshold": 0.8})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["threshold"] == 0.8

    def test_threshold_zero(self, client, mock_memory):
        """threshold=0.0 is a valid falsy value that must not be filtered out."""
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "threshold": 0.0})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["threshold"] == 0.0

    def test_threshold_omitted_uses_memory_default(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "threshold" not in kwargs


# ===========================================================================
# SearchRequest: top_k + threshold together
# ===========================================================================

class TestSearchLimitAndThreshold:

    def test_both_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "top_k": 10, "threshold": 0.5
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["top_k"] == 10
        assert kwargs["threshold"] == 0.5


# ===========================================================================
# MemoryCreate: infer parameter
# ===========================================================================

class TestAddInfer:
    """Verify that the infer parameter is accepted and forwarded to Memory.add()."""

    def test_infer_false_forwarded(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "Store this exactly"}],
            "user_id": "u1",
            "infer": False,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["infer"] is False

    def test_infer_true_forwarded(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "u1",
            "infer": True,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["infer"] is True

    def test_infer_omitted_uses_memory_default(self, client, mock_memory):
        """When infer is not sent, it should not appear in kwargs,
        allowing Memory.add() to use its own default (True)."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hello"}],
            "user_id": "u1",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "infer" not in kwargs


# ===========================================================================
# MemoryCreate: memory_type parameter
# ===========================================================================

class TestAddMemoryType:
    """Verify that the memory_type parameter is accepted and forwarded."""

    def test_memory_type_forwarded(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "u1",
            "memory_type": "core",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["memory_type"] == "core"

    def test_memory_type_omitted(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hello"}],
            "user_id": "u1",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "memory_type" not in kwargs


# ===========================================================================
# MemoryCreate: prompt parameter
# ===========================================================================

class TestAddPrompt:
    """Verify that the prompt parameter is accepted and forwarded."""

    def test_prompt_forwarded(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "u1",
            "prompt": "Extract food preferences only.",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["prompt"] == "Extract food preferences only."

    def test_prompt_omitted(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hello"}],
            "user_id": "u1",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "prompt" not in kwargs


# ===========================================================================
# MemoryCreate: all new params together
# ===========================================================================

class TestAddAllNewParams:

    def test_infer_memory_type_and_prompt_together(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "u1",
            "infer": False,
            "memory_type": "core",
            "prompt": "Custom extraction prompt.",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["infer"] is False
        assert kwargs["memory_type"] == "core"
        assert kwargs["prompt"] == "Custom extraction prompt."


# ===========================================================================
# Edge cases: falsy-but-valid values must not be filtered out
# ===========================================================================

class TestFalsyValues:
    """The handler filters with `v is not None`. Falsy values like False, 0,
    0.0, and empty string must still be forwarded."""

    def test_infer_false_not_filtered(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "infer": False,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["infer"] is False

    def test_threshold_zero_not_filtered(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "threshold": 0.0,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["threshold"] == 0.0


# ===========================================================================
# Extra/unknown fields are still silently ignored (existing Pydantic behavior)
# ===========================================================================

class TestUnknownFieldsIgnored:

    def test_unknown_search_field_ignored(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "bogus_field": "xyz",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "bogus_field" not in kwargs

    def test_unknown_add_field_ignored(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "unknown_param": 42,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "unknown_param" not in kwargs


# ===========================================================================
# Backward compatibility: existing params still work
# ===========================================================================

class TestExistingParamsUnchanged:

    def test_search_filters_still_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food",
            "user_id": "u1",
            "agent_id": "a1",
            "filters": {"category": "food"},
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["user_id"] == "u1"
        assert kwargs["agent_id"] == "a1"
        assert kwargs["filters"] == {"category": "food"}

    def test_add_metadata_still_forwarded(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "agent_id": "a1",
            "metadata": {"source": "test"},
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["user_id"] == "u1"
        assert kwargs["agent_id"] == "a1"
        assert kwargs["metadata"] == {"source": "test"}


# ===========================================================================
# OpenAPI schema: new fields are documented
# ===========================================================================

class TestOpenAPISchema:
    """Verify the new fields appear in the auto-generated OpenAPI schema."""

    def test_search_schema_includes_limit(self, client):
        schema = client.get("/openapi.json").json()
        search_props = schema["components"]["schemas"]["SearchRequest"]["properties"]
        assert "top_k" in search_props
        assert search_props["top_k"]["description"] == "Maximum number of results to return."

    def test_search_schema_includes_threshold(self, client):
        schema = client.get("/openapi.json").json()
        search_props = schema["components"]["schemas"]["SearchRequest"]["properties"]
        assert "threshold" in search_props

    def test_add_schema_includes_infer(self, client):
        schema = client.get("/openapi.json").json()
        add_props = schema["components"]["schemas"]["MemoryCreate"]["properties"]
        assert "infer" in add_props

    def test_add_schema_includes_memory_type(self, client):
        schema = client.get("/openapi.json").json()
        add_props = schema["components"]["schemas"]["MemoryCreate"]["properties"]
        assert "memory_type" in add_props

    def test_add_schema_includes_prompt(self, client):
        schema = client.get("/openapi.json").json()
        add_props = schema["components"]["schemas"]["MemoryCreate"]["properties"]
        assert "prompt" in add_props


# ===========================================================================
# Pydantic type validation: invalid types return 422
# ===========================================================================

class TestTypeValidation:
    """Verify FastAPI/Pydantic rejects invalid types with 422."""

    def test_limit_string_rejected(self, client):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "top_k": "not_a_number",
        })
        assert resp.status_code == 422

    def test_threshold_string_rejected(self, client):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "threshold": "high",
        })
        assert resp.status_code == 422

    def test_infer_string_coerced_by_pydantic(self, client, mock_memory):
        """Pydantic v2 coerces truthy strings like 'yes' to True for bool fields."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "infer": "yes",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert kwargs["infer"] is True

    def test_infer_invalid_value_rejected(self, client):
        """A value that cannot be coerced to bool should be rejected."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "infer": [1, 2, 3],
        })
        assert resp.status_code == 422

    def test_limit_float_rejected(self, client):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "top_k": 5.7,
        })
        assert resp.status_code == 422

    def test_memory_type_int_rejected(self, client):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "memory_type": 123,
        })
        assert resp.status_code == 422


# ===========================================================================
# Explicit null values: treated as omitted (filtered by `is not None`)
# ===========================================================================

class TestExplicitNull:
    """When a client sends null for an optional field, it should be treated
    as omitted — the Memory class default should be used."""

    def test_limit_null_uses_memory_default(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "top_k": None,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "top_k" not in kwargs

    def test_infer_null_uses_memory_default(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "infer": None,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "infer" not in kwargs

    def test_prompt_null_uses_memory_default(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_id": "u1",
            "prompt": None,
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        assert "prompt" not in kwargs


# ===========================================================================
# Verify exact call signatures match Memory method params
# ===========================================================================

class TestCallSignatureMatch:
    """Ensure forwarded params exactly match Memory.add() and Memory.search()
    keyword argument names — a typo here would cause a TypeError at runtime."""

    def test_search_kwargs_are_valid(self, client, mock_memory):
        """All kwargs forwarded to Memory.search() must be in its signature."""
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "agent_id": "a1",
            "run_id": "r1", "filters": {"k": "v"},
            "top_k": 10, "threshold": 0.5,
        })
        assert resp.status_code == 200
        # The handler passes query= as a keyword arg, so it appears in kwargs too
        _, kwargs = mock_memory.search.call_args
        valid_params = {"query", "user_id", "agent_id", "run_id", "top_k", "filters", "threshold", "rerank"}
        for key in kwargs:
            assert key in valid_params, f"Unexpected kwarg '{key}' forwarded to Memory.search()"

    def test_add_kwargs_are_valid(self, client, mock_memory):
        """All kwargs forwarded to Memory.add() must be in its signature."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hi"}],
            "user_id": "u1", "agent_id": "a1", "run_id": "r1",
            "metadata": {"k": "v"},
            "infer": False, "memory_type": "core", "prompt": "custom",
        })
        assert resp.status_code == 200
        # The handler passes messages= as a keyword arg, so it appears in kwargs too
        _, kwargs = mock_memory.add.call_args
        valid_params = {"messages", "user_id", "agent_id", "run_id", "metadata", "infer", "memory_type", "prompt"}
        for key in kwargs:
            assert key in valid_params, f"Unexpected kwarg '{key}' forwarded to Memory.add()"

    def test_messages_excluded_from_params_dict(self, client, mock_memory):
        """messages is passed separately via messages= kwarg, not duplicated from model_dump."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hi"}],
            "user_id": "u1",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.add.call_args
        # messages should be present (passed explicitly) and be a list of dicts
        assert "messages" in kwargs
        assert isinstance(kwargs["messages"], list)
        assert kwargs["messages"][0] == {"role": "user", "content": "hi"}

    def test_query_passed_explicitly(self, client, mock_memory):
        """query is passed as an explicit keyword arg to Memory.search()."""
        resp = client.post("/search", json={"query": "food", "user_id": "u1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["query"] == "food"


# ===========================================================================
# MemoryUpdate: text and metadata forwarding (fix for #3933)
# ===========================================================================

class TestUpdateMemory:
    """Verify that PUT /memories/{id} extracts text and metadata from the
    request body and forwards them correctly to Memory.update()."""

    def test_text_forwarded_as_data(self, client, mock_memory):
        resp = client.put("/memories/mem-1", json={"text": "Likes tennis"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.update.call_args
        assert kwargs["data"] == "Likes tennis"

    def test_metadata_forwarded(self, client, mock_memory):
        resp = client.put("/memories/mem-1", json={
            "text": "Likes tennis",
            "metadata": {"category": "sports"},
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.update.call_args
        assert kwargs["metadata"] == {"category": "sports"}

    def test_metadata_omitted_passes_none(self, client, mock_memory):
        resp = client.put("/memories/mem-1", json={"text": "Likes tennis"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.update.call_args
        assert kwargs["metadata"] is None

    def test_missing_text_returns_422(self, client):
        """text is required — omitting it should fail validation."""
        resp = client.put("/memories/mem-1", json={"metadata": {"k": "v"}})
        assert resp.status_code == 422

    def test_dict_not_passed_as_data(self, client, mock_memory):
        """Regression test for #3933: the entire dict must NOT be passed as data."""
        resp = client.put("/memories/mem-1", json={"text": "updated content"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.update.call_args
        assert isinstance(kwargs["data"], str)


class TestUpdateOpenAPISchema:
    """Verify the MemoryUpdate schema appears in the OpenAPI docs."""

    def test_update_schema_includes_text(self, client):
        schema = client.get("/openapi.json").json()
        update_props = schema["components"]["schemas"]["MemoryUpdate"]["properties"]
        assert "text" in update_props

    def test_update_schema_includes_metadata(self, client):
        schema = client.get("/openapi.json").json()
        update_props = schema["components"]["schemas"]["MemoryUpdate"]["properties"]
        assert "metadata" in update_props

# ===========================================================================
# GetMemories: Entity parameters to filters mapping (fix for #4955)
# ===========================================================================

class TestGetMemories:
    """Verify that GET /memories correctly maps entity parameters to the filters dict."""

    def test_get_memories_entity_filters_routing(self, client, mock_memory):
        """
        Issue #4955: Test that the GET /memories route correctly handles 
        top-level entity parameters by mapping them to the filters dictionary
        instead of passing them as direct kwargs to get_all()
        """
        # Send a request with a valid top-level entity parameter
        response = client.get("/memories?user_id=test_routing_user")
        
        # 1. Verify the endpoint doesn't crash with a 500 error
        assert response.status_code == 200
        
        # 2. Verify the response is structured correctly
        data = response.json()
        assert isinstance(data, list)
        
        # 3. Verify the core logic: the param was mapped to the filters dict!
        _, kwargs = mock_memory.get_all.call_args
        assert kwargs["filters"] == {"user_id": "test_routing_user"}
