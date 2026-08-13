"""Tests for self-hosted Mem0 server support (MEM0_BASE_URL routing).

Covers:
1. Default (no override) stays on the hosted Platform -- no behavior change.
2. An explicit override (env var or settings.json) routes to the self-hosted
   server: different URLs, X-API-Key auth, agent_id instead of app_id.
3. A malformed/empty override never silently falls back to the hosted
   Platform -- it is treated as self-hosted and fails closed instead of
   leaking requests to api.mem0.ai.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


# --------------------------------------------------------------------------- #
# resolve_base_url() -- config plumbing                                       #
# --------------------------------------------------------------------------- #
def test_resolve_base_url_defaults_to_hosted_platform(monkeypatch):
    from _identity import DEFAULT_BASE_URL, resolve_base_url

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert resolve_base_url() == DEFAULT_BASE_URL == "https://api.mem0.ai"


def test_resolve_base_url_env_var_overrides(monkeypatch):
    from _identity import resolve_base_url

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert resolve_base_url() == "http://localhost:8000"


def test_resolve_base_url_strips_trailing_slash(monkeypatch):
    from _identity import resolve_base_url

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000/")
    assert resolve_base_url() == "http://localhost:8000"


def test_resolve_base_url_falls_back_to_settings_file(monkeypatch, tmp_path):
    import load_settings
    from _identity import resolve_base_url

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"base_url": "http://self-hosted.local:8000"}))
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", settings_path)

    assert resolve_base_url() == "http://self-hosted.local:8000"


def test_resolve_base_url_env_var_takes_precedence_over_settings(monkeypatch, tmp_path):
    import load_settings
    from _identity import resolve_base_url

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"base_url": "http://from-settings:8000"}))
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", settings_path)
    monkeypatch.setenv("MEM0_BASE_URL", "http://from-env:9000")

    assert resolve_base_url() == "http://from-env:9000"


def test_resolve_base_url_empty_env_var_falls_through(monkeypatch, tmp_path):
    """A blank MEM0_BASE_URL must not be treated as an explicit override."""
    import load_settings
    from _identity import DEFAULT_BASE_URL, resolve_base_url

    monkeypatch.setenv("MEM0_BASE_URL", "   ")
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", settings_path)

    assert resolve_base_url() == DEFAULT_BASE_URL


# --------------------------------------------------------------------------- #
# is_self_hosted()                                                            #
# --------------------------------------------------------------------------- #
def test_is_self_hosted_false_by_default(monkeypatch):
    from _api import is_self_hosted

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert is_self_hosted() is False


def test_is_self_hosted_true_when_overridden(monkeypatch):
    from _api import is_self_hosted

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert is_self_hosted() is True


def test_is_self_hosted_malformed_url_treated_as_self_hosted(monkeypatch):
    """A garbage override must not be silently coerced back to the hosted URL."""
    from _api import is_self_hosted

    monkeypatch.setenv("MEM0_BASE_URL", "not-a-url")
    assert is_self_hosted() is True


# --------------------------------------------------------------------------- #
# auth_headers() / project_field()                                           #
# --------------------------------------------------------------------------- #
def test_auth_headers_hosted_uses_token(monkeypatch):
    from _api import auth_headers

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert auth_headers("m0-secret") == {"Authorization": "Token m0-secret"}


def test_auth_headers_self_hosted_uses_api_key_header(monkeypatch):
    from _api import auth_headers

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert auth_headers("m0sk-secret") == {"X-API-Key": "m0sk-secret"}


def test_project_field_hosted_is_app_id(monkeypatch):
    from _api import project_field

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert project_field() == "app_id"


def test_project_field_self_hosted_is_agent_id(monkeypatch):
    from _api import project_field

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert project_field() == "agent_id"


# --------------------------------------------------------------------------- #
# URL builders                                                                #
# --------------------------------------------------------------------------- #
def test_add_url_hosted(monkeypatch):
    from _api import add_url

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert add_url() == "https://api.mem0.ai/v3/memories/add/"


def test_add_url_self_hosted(monkeypatch):
    from _api import add_url

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert add_url() == "http://localhost:8000/memories"


def test_search_url_hosted(monkeypatch):
    from _api import search_url

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert search_url() == "https://api.mem0.ai/v3/memories/search/"


def test_search_url_self_hosted(monkeypatch):
    from _api import search_url

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert search_url() == "http://localhost:8000/search"


def test_delete_url_hosted(monkeypatch):
    from _api import delete_url

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    assert delete_url("mem-123") == "https://api.mem0.ai/v1/memories/mem-123/"


def test_delete_url_self_hosted(monkeypatch):
    from _api import delete_url

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    assert delete_url("mem-123") == "http://localhost:8000/memories/mem-123"


def test_search_url_malformed_override_does_not_leak_to_hosted(monkeypatch):
    """A garbage override must build a URL against itself, never api.mem0.ai."""
    from _api import search_url

    monkeypatch.setenv("MEM0_BASE_URL", "not-a-url")
    url = search_url()
    assert "api.mem0.ai" not in url
    assert url == "not-a-url/search"


# --------------------------------------------------------------------------- #
# End-to-end: write path (auto_import.post_memory)                            #
# --------------------------------------------------------------------------- #
def test_auto_import_post_memory_hosted_unchanged(monkeypatch):
    """Default (no override) still posts to the hosted Platform with app_id."""
    from auto_import import post_memory

    monkeypatch.delenv("MEM0_BASE_URL", raising=False)
    captured = {}

    def mock_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = req.headers
        captured.update(json.loads(req.data.decode("utf-8")))
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        result = post_memory("test-key", "content", "user", "CLAUDE.md", "my-project", "main")

    assert result is True
    assert captured["url"] == "https://api.mem0.ai/v3/memories/add/"
    assert captured["headers"]["Authorization"] == "Token test-key"
    assert captured["app_id"] == "my-project"
    assert "agent_id" not in captured


def test_auto_import_post_memory_self_hosted_routes_correctly(monkeypatch):
    """MEM0_BASE_URL override posts to the self-hosted server with agent_id."""
    from auto_import import post_memory

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    captured = {}

    def mock_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = req.headers
        captured.update(json.loads(req.data.decode("utf-8")))
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        result = post_memory("m0sk-key", "content", "user", "CLAUDE.md", "my-project", "main")

    assert result is True
    assert captured["url"] == "http://localhost:8000/memories"
    assert captured["headers"]["X-api-key"] == "m0sk-key"
    assert captured["agent_id"] == "my-project"
    assert "app_id" not in captured


# --------------------------------------------------------------------------- #
# End-to-end: search path (_search.search_memories)                           #
# --------------------------------------------------------------------------- #
def test_search_memories_self_hosted_routes_correctly(monkeypatch):
    from _search import search_memories

    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")
    captured = {}

    def mock_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = req.headers
        captured.update(json.loads(req.data.decode("utf-8")))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("m0sk-key", "user", "proj", "query")

    assert captured["url"] == "http://localhost:8000/search"
    assert captured["headers"]["X-api-key"] == "m0sk-key"
    filters = captured["filters"]
    assert {"agent_id": "proj"} in filters["AND"]
    assert {"app_id": "proj"} not in filters["AND"]


def test_search_memories_malformed_base_url_fails_closed_not_hosted(monkeypatch):
    """A garbage override must fail (return []) rather than leak to api.mem0.ai.

    No urlopen mock here on purpose: urllib rejects the schemeless URL before
    any network I/O happens, proving the request never reaches a real host --
    hosted or otherwise. search_memories' broad except turns that into [].
    """
    from _search import search_memories

    monkeypatch.setenv("MEM0_BASE_URL", "not-a-url")

    with patch("urllib.request.urlopen") as mock_urlopen:
        results = search_memories("key", "user", "proj", "query")
        mock_urlopen.assert_not_called()

    assert results == []


# --------------------------------------------------------------------------- #
# Category-taxonomy scripts: no self-hosted equivalent, must skip cleanly     #
# --------------------------------------------------------------------------- #
def test_auto_setup_categories_skips_when_self_hosted(monkeypatch):
    import auto_setup_categories as asc

    monkeypatch.setattr(asc, "resolve_api_key", lambda: "m0sk-key")
    monkeypatch.setenv("MEM0_BASE_URL", "http://localhost:8000")

    calls = []
    monkeypatch.setattr(asc, "make_client", lambda: calls.append("make_client"))

    asc.main()

    assert calls == []
