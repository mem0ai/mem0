"""Tests that the MEM-5893 option-parity flags reach the correct request payload/params."""

from __future__ import annotations

from unittest.mock import patch

from mem0_cli.backend.platform import PlatformBackend
from mem0_cli.config import PlatformConfig


def _make_backend() -> PlatformBackend:
    return PlatformBackend(PlatformConfig(api_key="test-key", base_url="https://api.mem0.ai"))


class TestAddOptions:
    def test_new_fields_and_existing_fields_land_in_payload_together(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={"results": []}) as mock_request:
            backend.add(
                content="hello",
                user_id="alice",
                metadata={"source": "test"},
                expires="2099-01-01",
                custom_instructions="Extract only preferences.",
                agent_custom_instructions="Extract only tool outcomes.",
                custom_categories=[{"prefs": "user preferences"}],
                structured_data_schema={"type": "object"},
                timestamp=1700000000,
            )
        payload = mock_request.call_args.kwargs["json"]
        assert payload["custom_instructions"] == "Extract only preferences."
        assert payload["agent_custom_instructions"] == "Extract only tool outcomes."
        assert payload["custom_categories"] == [{"prefs": "user preferences"}]
        assert payload["structured_data_schema"] == {"type": "object"}
        assert payload["timestamp"] == 1700000000
        assert payload["metadata"] == {"source": "test"}
        assert payload["expiration_date"] == "2099-01-01"

    def test_omitted_fields_are_absent_from_payload(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={"results": []}) as mock_request:
            backend.add(content="hello", user_id="alice")
        payload = mock_request.call_args.kwargs["json"]
        assert "custom_instructions" not in payload
        assert "agent_custom_instructions" not in payload
        assert "custom_categories" not in payload
        assert "structured_data_schema" not in payload
        assert "timestamp" not in payload


class TestSearchOptions:
    def test_show_expired_reference_date_latest_only_reach_payload(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value=[]) as mock_request:
            backend.search(
                "query",
                show_expired=True,
                reference_date="2024-01-01",
                latest_only=True,
            )
        payload = mock_request.call_args.kwargs["json"]
        assert payload["show_expired"] is True
        assert payload["reference_date"] == "2024-01-01"
        assert payload["latest_only"] is True

    def test_keyword_and_fields_reach_payload(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value=[]) as mock_request:
            backend.search("query", keyword=True, fields=["memory", "score"])
        payload = mock_request.call_args.kwargs["json"]
        assert payload["keyword_search"] is True
        assert payload["fields"] == ["memory", "score"]

    def test_keyword_and_fields_omitted_are_absent_from_payload(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value=[]) as mock_request:
            backend.search("query")
        payload = mock_request.call_args.kwargs["json"]
        assert "keyword_search" not in payload
        assert "fields" not in payload


class TestListOptions:
    def test_show_expired_and_latest_only_are_top_level_not_in_filters(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value=[]) as mock_request:
            backend.list_memories(user_id="alice", show_expired=True, latest_only=True)
        payload = mock_request.call_args.kwargs["json"]
        assert payload["show_expired"] is True
        assert payload["latest_only"] is True
        assert "show_expired" not in payload.get("filters", {})
        assert "latest_only" not in payload.get("filters", {})


class TestUpdateOptions:
    def test_expires_and_timestamp_reach_payload(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={}) as mock_request:
            backend.update("mem-123", expiration_date="2099-01-01", timestamp=1700000000)
        payload = mock_request.call_args.kwargs["json"]
        assert payload["expiration_date"] == "2099-01-01"
        assert payload["timestamp"] == 1700000000


class TestDeleteOptions:
    def test_delete_linked_is_a_query_param_not_json_body(self):
        backend = _make_backend()
        with patch.object(backend, "_request", return_value={}) as mock_request:
            backend.delete(memory_id="mem-123", delete_linked=True)
        call = mock_request.call_args
        assert call.kwargs["params"]["delete_linked"] == "true"
        assert "json" not in call.kwargs
