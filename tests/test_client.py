"""Tests for MemoryClient entity parameter rejection."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_memory_client():
    """Create a mock MemoryClient for testing entity param rejection."""
    with patch("mem0.client.main.httpx.Client") as mock_httpx:
        # Create a mock client instance
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = MagicMock(
            json=lambda: {"org_id": "org1", "project_id": "proj1", "user_email": "test@test.com"},
            raise_for_status=lambda: None
        )
        mock_httpx.return_value = mock_http_client

        with patch("mem0.client.main.capture_client_event"):
            from mem0.client.main import MemoryClient
            client = MemoryClient(api_key="test-api-key")
            yield client


class TestSearchEntityParamRejection:
    """Tests that top-level entity params are rejected in search()."""

    def test_search_rejects_user_id_kwarg(self, mock_memory_client):
        """search() should reject user_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"user_id"):
            mock_memory_client.search("test query", user_id="u1")

    def test_search_rejects_agent_id_kwarg(self, mock_memory_client):
        """search() should reject agent_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"agent_id"):
            mock_memory_client.search("test query", agent_id="a1")

    def test_search_rejects_app_id_kwarg(self, mock_memory_client):
        """search() should reject app_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"app_id"):
            mock_memory_client.search("test query", app_id="app1")

    def test_search_rejects_run_id_kwarg(self, mock_memory_client):
        """search() should reject run_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"run_id"):
            mock_memory_client.search("test query", run_id="r1")

    def test_search_rejects_multiple_entity_params(self, mock_memory_client):
        """search() should reject multiple top-level entity params."""
        with pytest.raises(ValueError, match=r"user_id|agent_id"):
            mock_memory_client.search("test query", user_id="u1", agent_id="a1")


class TestGetAllEntityParamRejection:
    """Tests that top-level entity params are rejected in get_all()."""

    def test_get_all_rejects_user_id_kwarg(self, mock_memory_client):
        """get_all() should reject user_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"user_id"):
            mock_memory_client.get_all(user_id="u1")

    def test_get_all_rejects_agent_id_kwarg(self, mock_memory_client):
        """get_all() should reject agent_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"agent_id"):
            mock_memory_client.get_all(agent_id="a1")

    def test_get_all_rejects_app_id_kwarg(self, mock_memory_client):
        """get_all() should reject app_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"app_id"):
            mock_memory_client.get_all(app_id="app1")

    def test_get_all_rejects_run_id_kwarg(self, mock_memory_client):
        """get_all() should reject run_id as top-level kwarg."""
        with pytest.raises(ValueError, match=r"run_id"):
            mock_memory_client.get_all(run_id="r1")


class TestFilterOperatorPassthrough:
    """Tests that AND/OR/NOT filter operators are passed through to the API."""

    def test_search_passes_and_filters(self, mock_memory_client):
        """search() should pass AND filters to the API."""
        mock_memory_client.client.post.return_value = MagicMock(
            json=lambda: {"results": []},
            raise_for_status=lambda: None
        )

        mock_memory_client.search(
            "test query",
            filters={"AND": [{"user_id": "u1"}, {"created_at": {"gte": "2024-01-01"}}]}
        )

        # Verify the POST was called with filters intact
        call_args = mock_memory_client.client.post.call_args
        payload = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
        assert payload["filters"] == {"AND": [{"user_id": "u1"}, {"created_at": {"gte": "2024-01-01"}}]}

    def test_search_passes_or_filters(self, mock_memory_client):
        """search() should pass OR filters to the API."""
        mock_memory_client.client.post.return_value = MagicMock(
            json=lambda: {"results": []},
            raise_for_status=lambda: None
        )

        mock_memory_client.search(
            "test query",
            filters={"OR": [{"user_id": "u1"}, {"agent_id": "a1"}]}
        )

        call_args = mock_memory_client.client.post.call_args
        payload = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
        assert payload["filters"] == {"OR": [{"user_id": "u1"}, {"agent_id": "a1"}]}

    def test_search_passes_not_filters(self, mock_memory_client):
        """search() should pass NOT filters to the API."""
        mock_memory_client.client.post.return_value = MagicMock(
            json=lambda: {"results": []},
            raise_for_status=lambda: None
        )

        mock_memory_client.search(
            "test query",
            filters={"AND": [{"user_id": "u1"}, {"NOT": {"categories": {"in": ["spam"]}}}]}
        )

        call_args = mock_memory_client.client.post.call_args
        payload = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
        assert payload["filters"] == {"AND": [{"user_id": "u1"}, {"NOT": {"categories": {"in": ["spam"]}}}]}

    def test_search_passes_complex_nested_filters(self, mock_memory_client):
        """search() should pass complex nested AND/OR/NOT filters to the API."""
        mock_memory_client.client.post.return_value = MagicMock(
            json=lambda: {"results": []},
            raise_for_status=lambda: None
        )

        complex_filter = {
            "AND": [
                {"user_id": "u1"},
                {"created_at": {"gte": "2024-01-01"}},
                {"NOT": {"OR": [{"categories": {"in": ["spam"]}}, {"categories": {"in": ["test"]}}]}}
            ]
        }
        mock_memory_client.search("test query", filters=complex_filter)

        call_args = mock_memory_client.client.post.call_args
        payload = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
        assert payload["filters"] == complex_filter
