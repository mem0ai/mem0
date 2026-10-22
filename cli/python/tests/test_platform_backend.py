"""Tests for the Platform backend (mem0 Platform API client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mem0_cli.backend.platform import NotFoundError, PlatformBackend
from mem0_cli.config import PlatformConfig


def _make_backend() -> PlatformBackend:
    # api_key/base_url are only used to build the httpx client; every test here
    # patches _request, so no real network calls are made.
    return PlatformBackend(PlatformConfig(api_key="test-key", base_url="https://api.mem0.ai"))


class TestDeleteEntities:
    def test_multiple_entities_returns_all_results(self):
        backend = _make_backend()
        responses = {
            "/v2/entities/user/alice/": {"message": "user deleted"},
            "/v2/entities/agent/bob/": {"message": "agent deleted"},
        }
        with patch.object(backend, "_request") as mock_request:
            mock_request.side_effect = lambda method, path, **kw: responses[path]
            result = backend.delete_entities(user_id="alice", agent_id="bob")

        # Regression: previously only the last entity's response survived.
        assert result == {
            "user": {"message": "user deleted"},
            "agent": {"message": "agent deleted"},
        }
        assert mock_request.call_count == 2

    def test_single_entity_keyed_by_type(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={"message": "user deleted"}):
            result = backend.delete_entities(user_id="alice")
        assert result == {"user": {"message": "user deleted"}}

    def test_no_entities_raises(self):
        backend = _make_backend()

        with pytest.raises(ValueError):
            backend.delete_entities()


class TestHistory:
    def test_history_requests_endpoint(self):
        backend = _make_backend()
        entries = [{"event": "ADD", "new_memory": "hello"}]
        with patch.object(backend, "_request", return_value=entries) as mock_request:
            result = backend.history("abc-123")
        mock_request.assert_called_once_with(
            "GET",
            "/v1/memories/abc-123/history/",
            params={"source": "CLI"},
        )
        assert result == entries

    def test_history_unwraps_results_dict(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={"results": [{"event": "UPDATE"}]}):
            result = backend.history("abc-123")
        assert result == [{"event": "UPDATE"}]

    def test_history_404_raises_not_found(self):
        backend = _make_backend()
        resp = MagicMock(status_code=404)
        backend._client = MagicMock()
        backend._client.request.return_value = resp
        with pytest.raises(NotFoundError, match="Resource not found"):
            backend.history("missing-id")
        path = backend._client.request.call_args.args[1]
        assert path == "/v1/memories/missing-id/history/"
