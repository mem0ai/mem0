from unittest.mock import MagicMock, patch

import pytest

from mem0_cli.backend.platform import PlatformBackend
from mem0_cli.config import PlatformConfig


@pytest.fixture
def platform_backend():
    config = PlatformConfig(
        api_key="test-api-key",
        base_url="https://api.mem0.ai",
    )
    with patch("httpx.Client") as mock_client:
        mock_http_client = MagicMock()
        mock_client.return_value = mock_http_client
        backend = PlatformBackend(config)
        # Mock _request method to verify f-string paths
        backend._request = MagicMock()
        yield backend


def test_get_encodes_memory_id(platform_backend):
    platform_backend.get("mem/123?active#frag")
    platform_backend._request.assert_called_once_with(
        "GET",
        "/v1/memories/mem%2F123%3Factive%23frag/",
        params={"source": "CLI"},
    )


def test_update_encodes_memory_id(platform_backend):
    platform_backend.update("mem/123?active#frag", content="updated")
    platform_backend._request.assert_called_once_with(
        "PUT",
        "/v1/memories/mem%2F123%3Factive%23frag/",
        json={"text": "updated", "source": "CLI"},
    )


def test_delete_encodes_memory_id(platform_backend):
    platform_backend.delete("mem/123?active#frag")
    platform_backend._request.assert_called_once_with(
        "DELETE",
        "/v1/memories/mem%2F123%3Factive%23frag/",
        params={"source": "CLI"},
    )


def test_delete_entities_encodes_entity_ids(platform_backend):
    platform_backend.delete_entities(
        user_id="user/123?active#frag",
        agent_id="agent/456?active#frag",
    )
    # Since delete_entities loops, assert it's called for both encoded IDs
    calls = platform_backend._request.call_args_list
    assert len(calls) == 2

    # Check call for user_id
    assert calls[0][0] == ("DELETE", "/v2/entities/user/user%2F123%3Factive%23frag/")
    assert calls[0][1] == {"params": {"source": "CLI"}}

    # Check call for agent_id
    assert calls[1][0] == ("DELETE", "/v2/entities/agent/agent%2F456%3Factive%23frag/")
    assert calls[1][1] == {"params": {"source": "CLI"}}


def test_get_event_encodes_event_id(platform_backend):
    platform_backend.get_event("evt/123?active#frag")
    platform_backend._request.assert_called_once_with(
        "GET",
        "/v1/event/evt%2F123%3Factive%23frag/",
    )
