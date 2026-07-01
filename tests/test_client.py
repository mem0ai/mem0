"""Tests for MemoryClient entity parameter rejection."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import requests


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

    @pytest.mark.parametrize("query", ["", "   ", "\n\t"])
    def test_search_rejects_empty_query(self, mock_memory_client, query):
        """search() should reject empty or whitespace-only queries before API calls."""
        with pytest.raises(ValueError, match="Invalid query.*empty or whitespace-only"):
            mock_memory_client.search(query, filters={"user_id": "u1"})

        mock_memory_client.client.post.assert_not_called()

    def test_search_trims_query_before_api_call(self, mock_memory_client):
        """search() should send the normalized query to the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_memory_client.client.post.return_value = mock_response

        mock_memory_client.search("  test query  ", filters={"user_id": "u1"})

        mock_memory_client.client.post.assert_called_once_with(
            "/v3/memories/search/",
            json={"query": "test query", "filters": {"user_id": "u1"}},
        )

    def test_search_passes_show_expired(self, mock_memory_client):
        """search() should pass show_expired to the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_memory_client.client.post.return_value = mock_response

        mock_memory_client.search("test query", filters={"user_id": "u1"}, show_expired=True)

        mock_memory_client.client.post.assert_called_once_with(
            "/v3/memories/search/",
            json={"query": "test query", "filters": {"user_id": "u1"}, "show_expired": True},
        )

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

    def test_get_all_passes_show_expired(self, mock_memory_client):
        """get_all() should pass show_expired to the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_memory_client.client.post.return_value = mock_response

        mock_memory_client.get_all(filters={"user_id": "u1"}, show_expired=True)

        mock_memory_client.client.post.assert_called_once_with(
            "/v3/memories/",
            json={"filters": {"user_id": "u1"}, "show_expired": True},
        )


class TestUpdateExpirationDate:
    """Tests for update expiration_date payload handling."""

    def test_update_preserves_null_expiration_date(self, mock_memory_client):
        """update() should send expiration_date=None so the API can clear it."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "mem_1", "expiration_date": None}
        mock_response.raise_for_status.return_value = None
        mock_memory_client.client.put.return_value = mock_response

        mock_memory_client.update("mem_1", expiration_date=None)

        mock_memory_client.client.put.assert_called_once_with(
            "/v1/memories/mem_1/",
            json={"expiration_date": None},
            params={},
        )


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


class TestDeleteLinked:
    """delete() should forward the opt-in delete_linked flag as a query param."""

    def _setup_delete(self, client):
        client.client.delete.return_value = MagicMock(
            json=lambda: {"message": "Memory deleted successfully!"},
            raise_for_status=lambda: None,
        )

    def test_delete_default_omits_delete_linked(self, mock_memory_client):
        """Default delete sends no delete_linked param — byte-identical to before."""
        self._setup_delete(mock_memory_client)

        mock_memory_client.delete("mem_123")

        call_args = mock_memory_client.client.delete.call_args
        assert call_args.args[0] == "/v1/memories/mem_123/"
        assert "delete_linked" not in call_args.kwargs.get("params", {})

    def test_delete_linked_true_sets_param(self, mock_memory_client):
        """delete_linked=True forwards delete_linked into the request params."""
        self._setup_delete(mock_memory_client)

        mock_memory_client.delete("mem_123", delete_linked=True)

        call_args = mock_memory_client.client.delete.call_args
        assert call_args.kwargs.get("params", {}).get("delete_linked") is True

    def test_delete_linked_false_omits_param(self, mock_memory_client):
        """delete_linked=False is stripped, so the default path is untouched."""
        self._setup_delete(mock_memory_client)

        mock_memory_client.delete("mem_123", delete_linked=False)

        call_args = mock_memory_client.client.delete.call_args
        assert "delete_linked" not in call_args.kwargs.get("params", {})


class TestPathSegmentEncoding:
    """Path params should remain one URL segment even when IDs contain URL syntax."""

    def _setup_response(self):
        return MagicMock(json=lambda: {"message": "ok"}, raise_for_status=lambda: None)

    def _called_paths(self, mock_method):
        return [call.args[0] for call in mock_method.call_args_list]

    def test_sync_memory_id_path_segments_are_encoded(self, mock_memory_client):
        mock_memory_client.client.get.return_value = self._setup_response()
        mock_memory_client.client.put.return_value = self._setup_response()
        mock_memory_client.client.delete.return_value = self._setup_response()

        memory_id = "mem/a?b#c"

        mock_memory_client.get(memory_id)
        mock_memory_client.update(memory_id, text="updated")
        mock_memory_client.delete(memory_id)
        mock_memory_client.history(memory_id)

        assert "/v1/memories/mem%2Fa%3Fb%23c/" in self._called_paths(mock_memory_client.client.get)
        assert mock_memory_client.client.put.call_args.args[0] == "/v1/memories/mem%2Fa%3Fb%23c/"
        assert mock_memory_client.client.delete.call_args.args[0] == "/v1/memories/mem%2Fa%3Fb%23c/"
        assert "/v1/memories/mem%2Fa%3Fb%23c/history/" in self._called_paths(mock_memory_client.client.get)

    def test_sync_entity_path_segments_are_encoded(self, mock_memory_client):
        mock_memory_client.client.delete.return_value = self._setup_response()

        mock_memory_client.delete_users(user_id="org/team?active#frag")

        assert mock_memory_client.client.delete.call_args.args[0] == (
            "/v2/entities/user/org%2Fteam%3Factive%23frag/"
        )

    def test_async_memory_id_path_segments_are_encoded(self):
        asyncio.run(self._assert_async_memory_id_path_segments_are_encoded())

    async def _assert_async_memory_id_path_segments_are_encoded(self):
        from mem0.client.main import AsyncMemoryClient

        client = AsyncMemoryClient.__new__(AsyncMemoryClient)
        client.async_client = MagicMock()
        client.async_client.get = AsyncMock(return_value=self._setup_response())
        client.async_client.put = AsyncMock(return_value=self._setup_response())
        client.async_client.delete = AsyncMock(return_value=self._setup_response())

        memory_id = "mem/a?b#c"

        with patch("mem0.client.main.capture_client_event"):
            await client.get(memory_id)
            await client.update(memory_id, text="updated")
            await client.delete(memory_id)
            await client.history(memory_id)

        assert client.async_client.get.call_args_list[0].args[0] == "/v1/memories/mem%2Fa%3Fb%23c/"
        assert client.async_client.put.call_args.args[0] == "/v1/memories/mem%2Fa%3Fb%23c/"
        assert client.async_client.delete.call_args.args[0] == "/v1/memories/mem%2Fa%3Fb%23c/"
        assert client.async_client.get.call_args_list[1].args[0] == "/v1/memories/mem%2Fa%3Fb%23c/history/"

    def test_async_entity_path_segments_are_encoded(self):
        asyncio.run(self._assert_async_entity_path_segments_are_encoded())

    async def _assert_async_entity_path_segments_are_encoded(self):
        from mem0.client.main import AsyncMemoryClient

        client = AsyncMemoryClient.__new__(AsyncMemoryClient)
        client.async_client = MagicMock()
        client.async_client.delete = AsyncMock(return_value=self._setup_response())

        with patch("mem0.client.main.capture_client_event"):
            await client.delete_users(user_id="org/team?active#frag")

        assert client.async_client.delete.call_args.args[0] == (
            "/v2/entities/user/org%2Fteam%3Factive%23frag/"
        )


class TestValidateApiKeyHttpError:
    """_validate_api_key should surface a clear ValueError on a non-JSON HTTP error.

    A 5xx from a CDN/proxy often has an HTML body, so response.json() fails. The
    HTTP status must be checked before json() so the intended ValueError is raised
    instead of a confusing JSONDecodeError during client construction.
    """

    def test_sync_client_non_json_5xx_raises_clear_error(self):
        # HTML body from a CDN/proxy: json() fails, but raise_for_status() reports the 503.
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        error_response = httpx.Response(503, text="<html>503 Service Unavailable</html>", request=request)
        response = MagicMock()
        response.json.side_effect = json.JSONDecodeError("Expecting value", "<html>", 0)
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=request, response=error_response
        )

        with patch("mem0.client.main.httpx.Client") as mock_httpx:
            mock_http_client = MagicMock()
            mock_http_client.get.return_value = response
            mock_httpx.return_value = mock_http_client

            with patch("mem0.client.main.capture_client_event"):
                from mem0.client.main import MemoryClient

                with pytest.raises(ValueError) as exc_info:
                    MemoryClient(api_key="test-api-key")

        # The HTTP status must surface as the intended "Error: ..." ValueError,
        # not the raw JSONDecodeError from parsing the HTML body.
        assert not isinstance(exc_info.value, json.JSONDecodeError)
        assert "Error:" in str(exc_info.value)

    def test_async_client_non_json_5xx_raises_clear_error(self):
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        error_response = httpx.Response(503, text="<html>503 Service Unavailable</html>", request=request)
        response = MagicMock()
        response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
        http_error = requests.exceptions.HTTPError("Server error", response=error_response)
        response.raise_for_status.side_effect = http_error

        with patch("mem0.client.main.requests.get", return_value=response):
            with patch("mem0.client.main.capture_client_event"):
                from mem0.client.main import AsyncMemoryClient

                with pytest.raises(ValueError) as exc_info:
                    AsyncMemoryClient(api_key="test-api-key")

        assert not isinstance(exc_info.value, requests.exceptions.JSONDecodeError)
        assert "Error:" in str(exc_info.value)
