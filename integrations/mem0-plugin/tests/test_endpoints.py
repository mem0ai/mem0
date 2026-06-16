"""Tests for scripts/_endpoints.py — base-URL resolution and the egress guard.

These assert the "nenhum vínculo com cloud" guarantee:
  - in MEM0_LOCAL_ONLY mode, cloud hosts are refused and an unset/cloud base
    collapses to "" so callers no-op (never fall back to the cloud);
  - without MEM0_LOCAL_ONLY, the official cloud default is preserved.
"""

from __future__ import annotations

import importlib


def _fresh(monkeypatch, **env):
    """Reload _endpoints with a clean env (it reads os.environ at call time)."""
    for key in ("MEM0_LOCAL_ONLY", "OPENMEMORY_API_BASE", "MEM0_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import _endpoints
    return importlib.reload(_endpoints)


class TestResolveApiBase:
    def test_default_is_cloud_without_local_only(self, monkeypatch):
        e = _fresh(monkeypatch)
        assert e.resolve_api_base() == "https://api.mem0.ai"

    def test_explicit_base_wins(self, monkeypatch):
        e = _fresh(monkeypatch, OPENMEMORY_API_BASE="http://localhost:8765/")
        assert e.resolve_api_base() == "http://localhost:8765"

    def test_local_only_without_base_is_empty(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="1")
        assert e.resolve_api_base() == ""  # fail-closed, never cloud

    def test_local_only_with_local_base(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="true",
                   OPENMEMORY_API_BASE="http://memhost:8765")
        assert e.resolve_api_base() == "http://memhost:8765"

    def test_local_only_refuses_cloud_base(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="1",
                   OPENMEMORY_API_BASE="https://api.mem0.ai")
        assert e.resolve_api_base() == ""  # cloud base collapses to no-op


class TestEgressAllowed:
    def test_allows_everything_without_local_only(self, monkeypatch):
        e = _fresh(monkeypatch)
        assert e.egress_allowed("https://api.mem0.ai/v3/memories/search/") is True

    def test_local_only_blocks_cloud_hosts(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="1",
                   OPENMEMORY_API_BASE="http://memhost:8765")
        assert e.egress_allowed("https://api.mem0.ai/v3/memories/add/") is False
        assert e.egress_allowed("https://us.i.posthog.com/i/v0/e/") is False
        assert e.egress_allowed("https://mcp.mem0.ai/mcp/") is False

    def test_local_only_allows_configured_local_host(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="1",
                   OPENMEMORY_API_BASE="http://memhost:8765")
        assert e.egress_allowed("http://memhost:8765/v3/memories/search/") is True

    def test_local_only_blocks_other_local_host(self, monkeypatch):
        e = _fresh(monkeypatch, MEM0_LOCAL_ONLY="1",
                   OPENMEMORY_API_BASE="http://memhost:8765")
        assert e.egress_allowed("http://evil:9000/x") is False
