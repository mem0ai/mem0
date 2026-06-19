"""Tests for the project-scoped, user_id-agnostic MCP read tools (task_03).

These cover `search_memory` and `list_memories` from ``app.mcp_server`` and assert
the shared-read behavior mandated by ADR-003:

- reads are filtered by ``project`` and NEVER by ``user_id`` (shared across all
  machines on the local network — the hostname only feeds attribution on writes);
- a bounded default ``top_k`` is applied; results are ordered by semantic score
  blended with recency (``updated_at`` → ``created_at``), so the most recently
  changed fact wins over the stale version it supersedes (ADR-003 at read time);
- the memory client is reused via ``get_memory_client_safe`` (no per-call reconnect);
- a memory written by host ``maqA`` in project ``A`` is retrievable by a search
  issued as host ``maqB`` in project ``A`` (verified at the mock level: no
  ``user_id`` ends up in the filters, so cross-host reads work);
- a search scoped to project ``B`` does not surface project ``A`` memories.

The memory client is fully mocked, so these run without Qdrant/Ollama/LLM access.
"""

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Set a dummy key before importing modules that may build a client lazily.
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app import mcp_server
from app.utils import recency
from app.mcp_server import (
    DEFAULT_LIST_TOP_K,
    DEFAULT_SEARCH_TOP_K,
    list_memories,
    search_memory,
)


# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #
def _hit(mem_id, data, project, score=0.9, **payload):
    """Build a fake vector-store search hit (OutputData-like)."""
    base = {"data": data, "project": project, "hash": f"h-{mem_id}"}
    base.update(payload)
    return SimpleNamespace(id=mem_id, score=score, payload=base)


def _point(mem_id, data, project, **payload):
    """Build a fake vector-store list point (scroll-like)."""
    base = {"data": data, "project": project, "hash": f"h-{mem_id}"}
    base.update(payload)
    return SimpleNamespace(id=mem_id, payload=base)


def _make_client(search_return=None, list_return=None):
    """Create a mocked memory client with embedding + vector store."""
    client = MagicMock()
    client.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    client.vector_store.search.return_value = search_return or []
    client.vector_store.list.return_value = list_return or []
    return client


@pytest.fixture
def patched_client():
    """Patch get_memory_client_safe to return a fresh mocked client."""
    client = _make_client()
    with patch.object(mcp_server, "get_memory_client_safe", return_value=client) as p:
        yield client, p


# --------------------------------------------------------------------------- #
# search_memory — project filter, no user_id
# --------------------------------------------------------------------------- #
class TestSearchMemoryProjectScope:
    @pytest.mark.asyncio
    async def test_search_applies_project_filter(self, patched_client):
        client, _ = patched_client
        client.vector_store.search.return_value = [_hit("1", "coffee", "A")]

        mcp_server.user_id_var.set("maqA")
        mcp_server.client_name_var.set("cursor")

        out = await search_memory("coffee", project="A")
        data = json.loads(out)

        filters = client.vector_store.search.call_args.kwargs["filters"]
        assert filters["project"] == "A"
        assert data["results"][0]["memory"] == "coffee"
        assert data["results"][0]["project"] == "A"

    @pytest.mark.asyncio
    async def test_search_does_not_filter_by_user_id(self, patched_client):
        client, _ = patched_client
        client.vector_store.search.return_value = []

        # Even with a hostname present in the context, it must NOT be a filter.
        mcp_server.user_id_var.set("maqA")
        mcp_server.client_name_var.set("cursor")

        await search_memory("anything", project="A")

        filters = client.vector_store.search.call_args.kwargs["filters"]
        assert "user_id" not in filters
        assert filters == {"project": "A"}

    @pytest.mark.asyncio
    async def test_search_applies_default_top_k(self, patched_client):
        client, _ = patched_client
        await search_memory("q", project="A")
        assert client.vector_store.search.call_args.kwargs["top_k"] == DEFAULT_SEARCH_TOP_K
        assert DEFAULT_SEARCH_TOP_K == 20

    @pytest.mark.asyncio
    async def test_search_orders_by_score_without_timestamps(self, patched_client):
        client, _ = patched_client
        # With no timestamps, recency is neutral and order falls back to score.
        client.vector_store.search.return_value = [
            _hit("low", "low", "A", score=0.1),
            _hit("high", "high", "A", score=0.9),
        ]
        out = await search_memory("q", project="A")
        ids = [r["id"] for r in json.loads(out)["results"]]
        assert ids == ["high", "low"]

    @pytest.mark.asyncio
    async def test_search_recency_outranks_older_more_similar(self, patched_client):
        client, _ = patched_client
        # The "old" fact is a closer semantic match (higher score) but was last
        # changed years ago. The "new" fact is less similar but was UPDATED today
        # (despite an old created_at) — recency must surface it first. This is the
        # ADR-003 "recent wins" rule applied at read time, keyed off updated_at.
        now = datetime.now(timezone.utc)
        client.vector_store.search.return_value = [
            _hit(
                "old", "old fact", "A", score=0.95,
                created_at="2020-01-01T00:00:00+00:00",
                updated_at="2020-01-01T00:00:00+00:00",
            ),
            _hit(
                "new", "new fact", "A", score=0.80,
                created_at="2019-01-01T00:00:00+00:00",
                updated_at=now.isoformat(),
            ),
        ]
        out = await search_memory("q", project="A")
        ids = [r["id"] for r in json.loads(out)["results"]]
        assert ids == ["new", "old"]

    @pytest.mark.asyncio
    async def test_search_recency_weight_zero_is_pure_score(self, patched_client, monkeypatch):
        client, _ = patched_client
        # Disabling recency (weight 0) restores pure semantic ordering even when a
        # less-similar fact is far more recent.
        monkeypatch.setattr(recency, "SEARCH_RECENCY_WEIGHT", 0.0)
        now = datetime.now(timezone.utc)
        client.vector_store.search.return_value = [
            _hit("old", "old", "A", score=0.95, updated_at="2020-01-01T00:00:00+00:00"),
            _hit("new", "new", "A", score=0.80, updated_at=now.isoformat()),
        ]
        out = await search_memory("q", project="A")
        ids = [r["id"] for r in json.loads(out)["results"]]
        assert ids == ["old", "new"]

    @pytest.mark.asyncio
    async def test_search_requires_project(self, patched_client):
        out = await search_memory("q", project="")
        assert "project not provided" in out

    @pytest.mark.asyncio
    async def test_search_client_unavailable(self):
        with patch.object(mcp_server, "get_memory_client_safe", return_value=None):
            out = await search_memory("q", project="A")
        assert "unavailable" in out

    @pytest.mark.asyncio
    async def test_search_handles_backend_error(self, patched_client):
        client, _ = patched_client
        client.vector_store.search.side_effect = RuntimeError("qdrant down")
        out = await search_memory("q", project="A")
        assert "Error searching memory" in out

    @pytest.mark.asyncio
    async def test_search_reuses_client_no_reconnect(self, patched_client):
        client, getter = patched_client
        await search_memory("q1", project="A")
        await search_memory("q2", project="A")
        # One get per call, but each returns the SAME reused singleton client.
        assert getter.call_count == 2
        assert all(c.args == () for c in getter.call_args_list)


# --------------------------------------------------------------------------- #
# list_memories — project filter, no user_id
# --------------------------------------------------------------------------- #
class TestListMemoriesProjectScope:
    @pytest.mark.asyncio
    async def test_list_scoped_to_project(self, patched_client):
        client, _ = patched_client
        client.vector_store.list.return_value = [
            _point("1", "m1", "A"),
            _point("2", "m2", "A"),
        ]
        mcp_server.user_id_var.set("maqA")
        out = await list_memories(project="A")
        data = json.loads(out)

        filters = client.vector_store.list.call_args.kwargs["filters"]
        assert filters == {"project": "A"}
        assert {r["id"] for r in data["results"]} == {"1", "2"}

    @pytest.mark.asyncio
    async def test_list_does_not_filter_by_user_id(self, patched_client):
        client, _ = patched_client
        mcp_server.user_id_var.set("maqA")
        await list_memories(project="A")
        filters = client.vector_store.list.call_args.kwargs["filters"]
        assert "user_id" not in filters

    @pytest.mark.asyncio
    async def test_list_applies_default_top_k(self, patched_client):
        client, _ = patched_client
        await list_memories(project="A")
        assert client.vector_store.list.call_args.kwargs["top_k"] == DEFAULT_LIST_TOP_K
        assert DEFAULT_LIST_TOP_K == 20

    @pytest.mark.asyncio
    async def test_list_unwraps_tuple_return(self, patched_client):
        client, _ = patched_client
        # Qdrant scroll returns (points, next_page_offset).
        client.vector_store.list.return_value = (
            [_point("1", "m1", "A")],
            None,
        )
        out = await list_memories(project="A")
        data = json.loads(out)
        assert data["results"][0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_list_requires_project(self, patched_client):
        out = await list_memories(project="")
        assert "project not provided" in out

    @pytest.mark.asyncio
    async def test_list_client_unavailable(self):
        with patch.object(mcp_server, "get_memory_client_safe", return_value=None):
            out = await list_memories(project="A")
        assert "unavailable" in out

    @pytest.mark.asyncio
    async def test_list_handles_backend_error(self, patched_client):
        client, _ = patched_client
        client.vector_store.list.side_effect = RuntimeError("scroll failed")
        out = await list_memories(project="A")
        assert "Error getting memories" in out


# --------------------------------------------------------------------------- #
# Cross-host shared read (integration at the mock level) — ADR-003
# --------------------------------------------------------------------------- #
class TestSharedReadAcrossHosts:
    @pytest.mark.asyncio
    async def test_memory_written_by_maqA_readable_as_maqB(self, patched_client):
        """A memory in project A (written by maqA) is returned for a search run
        as maqB in project A — because the read filter carries no user_id."""
        client, _ = patched_client
        # Memory carries user_id=maqA in its payload (write-time attribution).
        client.vector_store.search.return_value = [
            _hit("m-A", "shared fact", "A", user_id="maqA")
        ]

        # Search executed as host maqB.
        mcp_server.user_id_var.set("maqB")
        mcp_server.client_name_var.set("windsurf")

        out = await search_memory("shared", project="A")
        data = json.loads(out)

        filters = client.vector_store.search.call_args.kwargs["filters"]
        assert "user_id" not in filters  # cross-host read is not blocked
        assert data["results"][0]["id"] == "m-A"
        assert data["results"][0]["memory"] == "shared fact"

    @pytest.mark.asyncio
    async def test_project_B_search_excludes_project_A(self, patched_client):
        """A project-B search must filter by project B; the backend would not
        return project-A items (simulated here by an empty backend result)."""
        client, _ = patched_client
        client.vector_store.search.return_value = []  # backend has only project A

        mcp_server.user_id_var.set("maqB")
        mcp_server.client_name_var.set("windsurf")

        out = await search_memory("shared", project="B")
        data = json.loads(out)

        filters = client.vector_store.search.call_args.kwargs["filters"]
        assert filters["project"] == "B"
        assert data["results"] == []
