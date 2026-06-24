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

from mem0.exceptions import ValidationError as Mem0ValidationError

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
# SearchRequest: explain parameter
# ===========================================================================

class TestSearchExplain:
    """Verify that the explain parameter is accepted and forwarded."""

    def test_explain_true_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "explain": True})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["explain"] is True

    def test_explain_false_forwarded(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1", "explain": False})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["explain"] is False

    def test_explain_omitted_uses_memory_default(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "explain" not in kwargs


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
        assert kwargs["filters"]["user_id"] == "u1"
        assert kwargs["filters"]["agent_id"] == "a1"
        assert kwargs["filters"]["category"] == "food"

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
        _, kwargs = mock_memory.search.call_args
        valid_params = {"query", "top_k", "filters", "threshold", "rerank"}
        for key in kwargs:
            assert key in valid_params, f"Unexpected kwarg '{key}' forwarded to Memory.search()"
        assert kwargs["filters"]["user_id"] == "u1"
        assert kwargs["filters"]["agent_id"] == "a1"
        assert kwargs["filters"]["run_id"] == "r1"
        assert kwargs["filters"]["k"] == "v"

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
        assert "top_k" not in kwargs

    def test_get_memories_entity_filters_forward_top_k(self, client, mock_memory):
        response = client.get("/memories?user_id=test_routing_user&top_k=1000")

        assert response.status_code == 200

        _, kwargs = mock_memory.get_all.call_args
        assert kwargs["filters"] == {"user_id": "test_routing_user"}
        assert kwargs["top_k"] == 1000

    def test_get_memories_admin_top_k_zero_not_defaulted(self, client, mock_memory):
        mock_memory.vector_store.list.return_value = []

        response = client.get("/memories?top_k=0")

        assert response.status_code == 200
        _, kwargs = mock_memory.vector_store.list.call_args
        assert kwargs["top_k"] == 0

    def test_get_memories_rejects_top_k_above_limit(self, client, mock_memory):
        response = client.get("/memories?user_id=test_routing_user&top_k=1001")

        assert response.status_code == 422
        mock_memory.get_all.assert_not_called()


# ===========================================================================
# SearchRequest: entity IDs mapped into filters (fix for server 502)
# ===========================================================================

class TestSearchEntityIdMapping:
    """Verify that POST /search maps top-level user_id / agent_id / run_id
    into the filters dict instead of forwarding them as kwargs, which would
    cause Memory.search() to raise ValueError in v3."""

    def test_user_id_mapped_to_filters(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "user_id": "u1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "user_id" not in kwargs
        assert kwargs["filters"]["user_id"] == "u1"

    def test_agent_id_mapped_to_filters(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "agent_id": "a1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "agent_id" not in kwargs
        assert kwargs["filters"]["agent_id"] == "a1"

    def test_run_id_mapped_to_filters(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food", "run_id": "r1"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert "run_id" not in kwargs
        assert kwargs["filters"]["run_id"] == "r1"

    def test_all_entity_ids_mapped(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food", "user_id": "u1", "agent_id": "a1", "run_id": "r1",
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["filters"] == {"user_id": "u1", "agent_id": "a1", "run_id": "r1"}

    def test_entity_ids_merged_with_explicit_filters(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food",
            "user_id": "u1",
            "filters": {"category": "food"},
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["filters"]["user_id"] == "u1"
        assert kwargs["filters"]["category"] == "food"

    def test_no_entity_ids_no_filters(self, client, mock_memory):
        resp = client.post("/search", json={"query": "food"})
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["filters"] == {}

    def test_only_filters_no_entity_ids(self, client, mock_memory):
        resp = client.post("/search", json={
            "query": "food",
            "filters": {"user_id": "u1", "category": "food"},
        })
        assert resp.status_code == 200
        _, kwargs = mock_memory.search.call_args
        assert kwargs["filters"]["user_id"] == "u1"
        assert kwargs["filters"]["category"] == "food"


class TestSearchValidationErrors:
    """Verify that ValueError from Memory.search() returns 400, not 502."""

    def test_empty_filters_returns_400(self, client, mock_memory):
        mock_memory.search.side_effect = ValueError(
            "filters must contain at least one of: user_id, agent_id, run_id"
        )
        resp = client.post("/search", json={"query": "food", "filters": {}})
        assert resp.status_code == 400
        assert "filters must contain" in resp.json()["detail"]

    def test_no_identifiers_returns_400(self, client, mock_memory):
        mock_memory.search.side_effect = ValueError(
            "filters must contain at least one of: user_id, agent_id, run_id"
        )
        resp = client.post("/search", json={"query": "food"})
        assert resp.status_code == 400


# ===========================================================================
# add / update / delete: map core errors to 4xx instead of 502
# ===========================================================================

class TestWriteHandlerErrorMapping:
    """ValueError("... not found") -> 404, other ValueError / Mem0ValidationError
    -> 400. A real outage still surfaces as 502 via upstream_error()."""

    def test_update_not_found_returns_404(self, client, mock_memory):
        mock_memory.update.side_effect = ValueError("Memory with id mem-1 not found")
        resp = client.put("/memories/mem-1", json={"text": "new"})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_delete_not_found_returns_404(self, client, mock_memory):
        mock_memory.delete.side_effect = ValueError("Memory with id mem-1 not found")
        resp = client.delete("/memories/mem-1")
        assert resp.status_code == 404

    def test_update_other_value_error_returns_400(self, client, mock_memory):
        mock_memory.update.side_effect = ValueError("data must be a non-empty string")
        resp = client.put("/memories/mem-1", json={"text": "new"})
        assert resp.status_code == 400

    def test_add_validation_error_returns_400(self, client, mock_memory):
        mock_memory.add.side_effect = Mem0ValidationError(
            message="messages must be str, dict, or list[dict]", error_code="VALIDATION_003"
        )
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hi"}], "user_id": "u1",
        })
        assert resp.status_code == 400

    def test_add_real_outage_still_returns_502(self, client, mock_memory):
        mock_memory.add.side_effect = RuntimeError("vector store unreachable")
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "hi"}], "user_id": "u1",
        })
        assert resp.status_code == 502


# ===========================================================================
# MemoryCreate.Message.content: multimodal content (image_url) — issue #5068
# ===========================================================================

class TestMultimodalContent:
    """Verify the /memories endpoint accepts multimodal content (e.g. image_url
    dicts and lists of parts), matching the format supported by Memory.add()
    via parse_vision_messages(). Previously the Pydantic schema only allowed
    `str`, which rejected the OpenAI-style multimodal payload with 422 before
    Memory.add() was ever invoked. Regression guard for issue #5068.
    """

    def test_image_url_dict_content_accepted(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/receipt.jpg"},
                    },
                }
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_memory.add.call_args
        sent_messages = kwargs["messages"]
        assert isinstance(sent_messages[0]["content"], dict)
        assert sent_messages[0]["content"]["type"] == "image_url"

    def test_list_of_parts_content_accepted(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/a.jpg"},
                        },
                    ],
                }
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_memory.add.call_args
        sent_messages = kwargs["messages"]
        assert isinstance(sent_messages[0]["content"], list)
        assert len(sent_messages[0]["content"]) == 2

    def test_plain_string_content_still_accepted(self, client, mock_memory):
        """Backward compatibility: plain string content must still work."""
        resp = client.post("/memories", json={
            "messages": [{"role": "user", "content": "I like pizza"}],
            "user_id": "alice",
        })
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_memory.add.call_args
        sent_messages = kwargs["messages"]
        assert sent_messages[0]["content"] == "I like pizza"

    def test_mixed_text_and_image_messages_accepted(self, client, mock_memory):
        resp = client.post("/memories", json={
            "messages": [
                {"role": "user", "content": "Here is the receipt"},
                {
                    "role": "user",
                    "content": {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/r.jpg"},
                    },
                },
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 200, resp.text
        _, kwargs = mock_memory.add.call_args
        sent_messages = kwargs["messages"]
        assert sent_messages[0]["content"] == "Here is the receipt"
        assert isinstance(sent_messages[1]["content"], dict)


    def test_image_content_rejected_when_vision_disabled(self, client, mock_memory):
        """Critical guard for #5068 follow-up: an image_url dict with vision NOT
        configured must return an explicit 422, not silently drop the content
        and return 200 with empty results."""
        mock_memory.config.llm.config.get.return_value = False
        resp = client.post("/memories", json={
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/receipt.jpg"},
                    },
                }
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 422, resp.text
        assert "vision" in resp.text.lower()
        mock_memory.add.assert_not_called()

    def test_list_image_content_rejected_when_vision_disabled(self, client, mock_memory):
        """A list containing an image part is also rejected when vision is off."""
        mock_memory.config.llm.config.get.return_value = False
        resp = client.post("/memories", json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is this?"},
                        {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}},
                    ],
                }
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 422, resp.text
        mock_memory.add.assert_not_called()

    def test_text_only_list_allowed_when_vision_disabled(self, client, mock_memory):
        """A list with only text parts carries no image content, so it must
        still be accepted even when vision is disabled."""
        mock_memory.config.llm.config.get.return_value = False
        resp = client.post("/memories", json={
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "I like pizza"}]}
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 200, resp.text
        mock_memory.add.assert_called_once()

    def test_malformed_text_part_returns_422_not_500(self, client, mock_memory):
        """A text part missing its 'text' key must be rejected by the request
        validator with a clean 422, not crash parse_vision_messages into a 500."""
        resp = client.post("/memories", json={
            "messages": [
                {"role": "user", "content": [{"type": "text"}]}
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 422, resp.text
        mock_memory.add.assert_not_called()

    def test_malformed_image_part_returns_422(self, client, mock_memory):
        """An image_url part missing image_url.url must be rejected with 422."""
        resp = client.post("/memories", json={
            "messages": [
                {"role": "user", "content": [{"type": "image_url"}]}
            ],
            "user_id": "alice",
        })
        assert resp.status_code == 422, resp.text
        mock_memory.add.assert_not_called()
