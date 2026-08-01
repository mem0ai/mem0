"""Tests for server/main.py's DEFAULT_CONFIG construction from env vars."""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

# server/ modules use bare imports (import telemetry, from auth import ...), so
# the server directory itself must be importable, mirroring how it runs in
# Docker. Mirrors tests/test_api_keys_router.py's guard.
_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)


def _reload_server_main(env: dict):
    """Reload server.main under a patched environment and return the module.

    DEFAULT_CONFIG is built at import time from os.environ, so each case
    needs a fresh reload rather than reading the already-imported module.
    """
    base_env = {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}
    with patch.dict(os.environ, {**base_env, **env}, clear=False):
        with patch("mem0.Memory.from_config", return_value=MagicMock()):
            import server.main as server_main
            importlib.reload(server_main)
            return server_main


class TestLLMBaseURL:
    def test_unset_omits_openai_base_url(self):
        mod = _reload_server_main({"MEM0_LLM_BASE_URL": ""})
        assert "openai_base_url" not in mod.DEFAULT_CONFIG["llm"]["config"]

    def test_set_forwarded_to_llm_config(self):
        mod = _reload_server_main({"MEM0_LLM_BASE_URL": "http://llm.internal:11434/v1"})
        assert mod.DEFAULT_CONFIG["llm"]["config"]["openai_base_url"] == "http://llm.internal:11434/v1"

    def test_does_not_affect_embedder_config(self):
        mod = _reload_server_main({"MEM0_LLM_BASE_URL": "http://llm.internal:11434/v1"})
        assert "openai_base_url" not in mod.DEFAULT_CONFIG["embedder"]["config"]


class TestEmbedderBaseURL:
    def test_unset_omits_openai_base_url(self):
        mod = _reload_server_main({"MEM0_EMBEDDER_BASE_URL": ""})
        assert "openai_base_url" not in mod.DEFAULT_CONFIG["embedder"]["config"]

    def test_set_forwarded_to_embedder_config(self):
        mod = _reload_server_main({"MEM0_EMBEDDER_BASE_URL": "http://embed.internal:8080/v1"})
        assert mod.DEFAULT_CONFIG["embedder"]["config"]["openai_base_url"] == "http://embed.internal:8080/v1"

    def test_does_not_affect_llm_config(self):
        mod = _reload_server_main({"MEM0_EMBEDDER_BASE_URL": "http://embed.internal:8080/v1"})
        assert "openai_base_url" not in mod.DEFAULT_CONFIG["llm"]["config"]


class TestBothIndependent:
    def test_llm_and_embedder_can_point_at_different_hosts(self):
        mod = _reload_server_main({
            "MEM0_LLM_BASE_URL": "http://llm.internal:11434/v1",
            "MEM0_EMBEDDER_BASE_URL": "http://embed.internal:8080/v1",
        })
        assert mod.DEFAULT_CONFIG["llm"]["config"]["openai_base_url"] == "http://llm.internal:11434/v1"
        assert mod.DEFAULT_CONFIG["embedder"]["config"]["openai_base_url"] == "http://embed.internal:8080/v1"
