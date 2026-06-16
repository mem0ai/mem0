"""Tests for the server-side fail-closed egress guard (MEM0_LOCAL_ONLY).

These lock in the in-code guarantee that, in team local-only mode, the memory
client is never built with an LLM/embedder that would reach a non-local (cloud)
host — so memory content can never leave the local network even if the DB/env
were (mis)configured for OpenAI/Anthropic/etc. No network or DB access.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils import memory


def _blk(provider, config=None):
    return {"provider": provider, "config": config or {}}


@pytest.mark.parametrize("value,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("false", False), ("", False), (None, False),
])
def test_is_local_only_parsing(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("MEM0_LOCAL_ONLY", raising=False)
    else:
        monkeypatch.setenv("MEM0_LOCAL_ONLY", value)
    assert memory.is_local_only() is expected


@pytest.mark.parametrize("host,expected", [
    ("localhost", True),
    ("127.0.0.1", True),
    ("host.docker.internal", True),
    ("mem0_store", True),            # bare docker service name
    ("ollama.internal", True),
    ("myhost.local", True),
    ("192.168.0.10", True),
    ("10.1.2.3", True),
    ("172.17.0.1", True),
    ("api.openai.com", False),
    ("us.i.posthog.com", False),
    ("8.8.8.8", False),
    ("", False),
])
def test_is_private_host(host, expected):
    assert memory._is_private_host(host) is expected


def test_provider_block_local_backends():
    assert memory._provider_block_is_local(_blk("ollama", {})) is True
    assert memory._provider_block_is_local(
        _blk("ollama", {"ollama_base_url": "http://host.docker.internal:11434"})) is True
    # llama.cpp wired through the openai provider pointing at a local server
    assert memory._provider_block_is_local(
        _blk("openai", {"openai_base_url": "http://192.168.0.10:8080/v1"})) is True


def test_provider_block_cloud_backends():
    # openai with no base URL hits api.openai.com
    assert memory._provider_block_is_local(_blk("openai", {})) is False
    assert memory._provider_block_is_local(
        _blk("openai", {"openai_base_url": "https://api.openai.com/v1"})) is False
    # ollama pointed at a public host is NOT local
    assert memory._provider_block_is_local(
        _blk("ollama", {"ollama_base_url": "https://ollama.example.com"})) is False
    # any other provider is a cloud provider
    assert memory._provider_block_is_local(_blk("anthropic", {"model": "claude"})) is False
    assert memory._provider_block_is_local(None) is False


def test_local_only_violations():
    cloud = {"llm": _blk("openai", {}), "embedder": _blk("openai", {})}
    assert memory._local_only_violations(cloud) == ["llm=openai", "embedder=openai"]

    mixed = {"llm": _blk("ollama", {}), "embedder": _blk("openai", {})}
    assert memory._local_only_violations(mixed) == ["embedder=openai"]

    local = {"llm": _blk("ollama", {}), "embedder": _blk("ollama", {})}
    assert memory._local_only_violations(local) == []


def test_get_memory_client_fails_closed_on_cloud_config(monkeypatch):
    """With MEM0_LOCAL_ONLY active and a cloud config, no client is built."""
    monkeypatch.setenv("MEM0_LOCAL_ONLY", "1")
    cloud_cfg = {
        "vector_store": {"provider": "qdrant", "config": {}},
        "llm": _blk("openai", {"api_key": "sk-test"}),
        "embedder": _blk("openai", {"api_key": "sk-test"}),
        "version": "v1.1",
    }
    monkeypatch.setattr(memory, "get_default_memory_config", lambda: cloud_cfg)
    # No DB override: force the DB load to be a no-op so the cloud default stands.
    monkeypatch.setattr(memory, "SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("no db")))

    # Sentinel so we can prove Memory.from_config is never reached.
    def _boom(*a, **k):
        raise AssertionError("Memory.from_config must NOT be called in local-only with a cloud config")
    monkeypatch.setattr(memory.Memory, "from_config", staticmethod(_boom))

    memory.reset_memory_client()
    assert memory.get_memory_client() is None
