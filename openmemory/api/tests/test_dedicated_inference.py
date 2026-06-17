"""Tests for dedicated inference service URL config (task_04 / ADR-002)."""

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def _clear_inference_env(monkeypatch):
    """Isolate tests from api/.env OLLAMA_BASE_URL and prior test pollution."""
    for key in (
        "OLLAMA_BASE_URL",
        "OLLAMA_EMBED_URL",
        "OLLAMA_LLM_URL",
        "LLM_BASE_URL",
        "EMBEDDER_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


class TestDedicatedServiceUrls:
    def test_ollama_embed_url_maps_to_embedder(self, monkeypatch):
        monkeypatch.setenv("EMBEDDER_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_EMBED_URL", "http://ollama-embed:11434")
        monkeypatch.setenv("QDRANT_HOST", "mem0_store")
        monkeypatch.setenv("QDRANT_PORT", "6333")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_LLM_URL", "http://ollama-llm:11434")

        from app.utils.memory import get_default_memory_config

        cfg = get_default_memory_config()
        assert cfg["embedder"]["config"]["ollama_base_url"] == "http://ollama-embed:11434"
        assert cfg["llm"]["config"]["ollama_base_url"] == "http://ollama-llm:11434"

    def test_llamacpp_openai_base_url(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_BASE_URL", "http://llama-server:8080/v1")
        monkeypatch.setenv("EMBEDDER_PROVIDER", "openai")
        monkeypatch.setenv("EMBEDDER_BASE_URL", "http://llama-server:8080/v1")
        monkeypatch.setenv("QDRANT_HOST", "mem0_store")
        monkeypatch.setenv("QDRANT_PORT", "6333")

        from app.utils.memory import get_default_memory_config

        cfg = get_default_memory_config()
        assert cfg["llm"]["config"]["openai_base_url"] == "http://llama-server:8080/v1"
        assert cfg["embedder"]["config"]["openai_base_url"] == "http://llama-server:8080/v1"

    def test_explicit_service_url_not_rewritten_for_docker(self, monkeypatch):
        monkeypatch.setenv("EMBEDDER_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_EMBED_URL", "http://ollama-embed:11434")
        monkeypatch.setenv("QDRANT_HOST", "mem0_store")
        monkeypatch.setenv("QDRANT_PORT", "6333")

        from app.utils.memory import _fix_ollama_urls_if_localhost

        block = {
            "provider": "ollama",
            "config": {"ollama_base_url": "http://ollama-embed:11434", "model": "nomic-embed-text"},
        }
        with patch("app.utils.memory._fix_ollama_urls") as fix:
            out = _fix_ollama_urls_if_localhost(block)
        fix.assert_not_called()
        assert out["config"]["ollama_base_url"] == "http://ollama-embed:11434"

    def test_localhost_url_still_rewritten_in_docker(self, monkeypatch):
        from app.utils.memory import _fix_ollama_urls_if_localhost

        block = {
            "provider": "ollama",
            "config": {"ollama_base_url": "http://localhost:11434", "model": "m"},
        }
        with patch("app.utils.memory._fix_ollama_urls", side_effect=lambda x: x) as fix:
            _fix_ollama_urls_if_localhost(block)
        fix.assert_called_once()

    def test_private_base_url_passes_local_only_guard(self):
        from app.utils.memory import _provider_block_is_local

        block = {
            "provider": "ollama",
            "config": {"ollama_base_url": "http://ollama-embed:11434", "model": "m"},
        }
        assert _provider_block_is_local(block) is True
