"""Tests for the hook REST transport adapter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def _response(payload: object, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__ = lambda value: value
    response.__exit__ = MagicMock(return_value=False)
    return response


def test_platform_is_the_unchanged_default(monkeypatch):
    from _api import add_memory

    monkeypatch.delenv("MEM0_API_BASE", raising=False)
    captured = {}

    def urlopen(request, timeout=None):
        captured["request"] = request
        return _response({"results": []})

    with patch("urllib.request.urlopen", side_effect=urlopen):
        add_memory("platform-key", {"messages": [], "user_id": "alice", "app_id": "repo"})

    request = captured["request"]
    assert request.full_url == "https://api.mem0.ai/v3/memories/add/"
    assert request.get_header("Authorization") == "Token platform-key"
    assert json.loads(request.data)["app_id"] == "repo"


def test_self_hosted_add_maps_app_id_and_auth(monkeypatch):
    from _api import add_memory

    monkeypatch.setenv("MEM0_API_BASE", "https://memory.example.test/")
    captured = {}

    def urlopen(request, timeout=None):
        captured["request"] = request
        return _response({"results": []}, status=201)

    with patch("urllib.request.urlopen", side_effect=urlopen):
        status, _ = add_memory(
            "self-hosted-key",
            {"messages": [], "user_id": "alice", "app_id": "repo"},
        )

    request = captured["request"]
    body = json.loads(request.data)
    assert status == 201
    assert request.full_url == "https://memory.example.test/memories"
    assert request.get_header("X-api-key") == "self-hosted-key"
    assert request.get_header("Authorization") is None
    assert body["agent_id"] == "repo"
    assert "app_id" not in body


def test_explicit_agent_id_wins_over_app_id(monkeypatch):
    from _api import add_memory

    monkeypatch.setenv("MEM0_API_BASE", "https://memory.example.test")
    captured = {}

    def urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data)
        return _response({"results": []})

    with patch("urllib.request.urlopen", side_effect=urlopen):
        add_memory(
            "key",
            {"messages": [], "user_id": "alice", "agent_id": "explicit", "app_id": "alias"},
        )

    assert captured["body"]["agent_id"] == "explicit"
    assert "app_id" not in captured["body"]


def test_self_hosted_search_maps_nested_app_id_and_drops_rerank(monkeypatch):
    from _api import search_memories

    monkeypatch.setenv("MEM0_API_BASE", "https://memory.example.test")
    captured = {}

    def urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data)
        return _response({"results": []})

    payload = {
        "query": "decisions",
        "filters": {"AND": [{"user_id": "alice"}, {"OR": [{"app_id": "repo"}]}]},
        "top_k": 3,
        "rerank": True,
    }
    with patch("urllib.request.urlopen", side_effect=urlopen):
        search_memories("key", payload)

    assert captured["body"]["filters"]["AND"][1] == {"OR": [{"agent_id": "repo"}]}
    assert "rerank" not in captured["body"]


def test_self_hosted_list_converts_supported_scopes_to_query(monkeypatch):
    from _api import list_memories

    monkeypatch.setenv("MEM0_API_BASE", "https://memory.example.test")
    captured = {}

    def urlopen(request, timeout=None):
        captured["request"] = request
        return _response({"results": []})

    with patch("urllib.request.urlopen", side_effect=urlopen):
        list_memories(
            "key",
            {
                "filters": {"AND": [{"user_id": "alice"}, {"app_id": "repo"}]},
                "page_size": 25,
            },
        )

    assert captured["request"].full_url == (
        "https://memory.example.test/memories?top_k=25&user_id=alice&agent_id=repo"
    )


def test_delete_memory_url_encodes_identifier(monkeypatch):
    from _api import delete_memory

    monkeypatch.setenv("MEM0_API_BASE", "https://memory.example.test")
    captured = {}

    def urlopen(request, timeout=None):
        captured["request"] = request
        return _response({"message": "deleted"})

    with patch("urllib.request.urlopen", side_effect=urlopen):
        delete_memory("key", "memory/with spaces")

    assert captured["request"].full_url == "https://memory.example.test/memories/memory%2Fwith%20spaces"
