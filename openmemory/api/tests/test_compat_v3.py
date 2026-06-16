"""Tests for the cloud-compatible /v3/memories shim used by local-only hooks.

Asserts the contract the plugin hooks rely on, backed by a fake memory client:
  - search is project-scoped (shared; user_id ignored) and post-filters by
    metadata type/threshold;
  - add concatenates messages, scopes by app_id=project, and preserves the
    hook-supplied metadata (type/file) by calling client.add directly;
  - list returns a count + results.
"""

import importlib.util
import sys
import types
from pathlib import Path

# The router only needs ``get_memory_client`` from app.utils.memory. Stub that
# module (and its parent packages) so we can path-load the router WITHOUT
# importing app.routers.__init__, which pulls heavy deps (fastapi_pagination,
# an import-time OpenAI() client) that aren't installed outside Docker.
for _name in ("app", "app.utils", "app.utils.memory"):
    sys.modules.setdefault(_name, types.ModuleType(_name))
sys.modules["app.utils.memory"].get_memory_client = lambda: None

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "compat_v3.py"
_spec = importlib.util.spec_from_file_location("compat_v3_under_test", _PATH)
compat_v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compat_v3)

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class _Hit:
    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


class _Embed:
    def embed(self, query, mode):  # noqa: D401
        return [0.1, 0.2, 0.3]


class _VectorStore:
    def __init__(self, hits):
        self._hits = hits

    def _scoped(self, filters):
        hits = self._hits
        if filters and "project" in filters:
            hits = [h for h in hits if h.payload.get("project") == filters["project"]]
        return hits

    def search(self, query, vectors, limit, filters):
        return self._scoped(filters)[:limit]

    def list(self, filters, top_k):
        return self._scoped(filters)[:top_k]


class _FakeClient:
    def __init__(self, hits):
        self.embedding_model = _Embed()
        self.vector_store = _VectorStore(hits)
        self.add_calls = []

    def add(self, text, **kwargs):
        self.add_calls.append((text, kwargs))
        return {"results": [{"id": "new-1", "memory": text, "event": "ADD"}]}


def _hits():
    return [
        _Hit("a1", 0.9, {"data": "alpha state", "project": "A", "type": "session_state"}),
        _Hit("a2", 0.4, {"data": "alpha decision", "project": "A", "type": "decision"}),
        _Hit("b1", 0.95, {"data": "beta secret", "project": "B", "type": "session_state"}),
    ]


@pytest_asyncio.fixture
async def client(monkeypatch):
    fake = _FakeClient(_hits())
    monkeypatch.setattr(compat_v3, "get_memory_client", lambda: fake)
    app = FastAPI()
    app.include_router(compat_v3.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac._fake = fake  # expose for assertions
        yield ac


def _and(*clauses):
    return {"AND": list(clauses)}


class TestSearch:
    @pytest.mark.asyncio
    async def test_project_scoped_excludes_other_projects(self, client):
        body = {"query": "state", "filters": _and({"user_id": "host"}, {"app_id": "A"})}
        data = (await client.post("/v3/memories/search/", json=body)).json()
        ids = {r["id"] for r in data["results"]}
        assert ids == {"a1", "a2"}  # only project A, user_id ignored

    @pytest.mark.asyncio
    async def test_metadata_type_post_filter(self, client):
        body = {
            "query": "state",
            "filters": _and({"app_id": "A"}, {"metadata": {"type": "session_state"}}),
        }
        data = (await client.post("/v3/memories/search/", json=body)).json()
        assert [r["id"] for r in data["results"]] == ["a1"]

    @pytest.mark.asyncio
    async def test_threshold_filters_low_scores(self, client):
        body = {"query": "state", "filters": _and({"app_id": "A"}), "threshold": 0.5}
        data = (await client.post("/v3/memories/search/", json=body)).json()
        assert [r["id"] for r in data["results"]] == ["a1"]  # a2 score 0.4 dropped

    @pytest.mark.asyncio
    async def test_result_shape(self, client):
        body = {"query": "state", "filters": _and({"app_id": "A"})}
        r = (await client.post("/v3/memories/search/", json=body)).json()["results"][0]
        for key in ("id", "memory", "score", "metadata"):
            assert key in r


class TestAdd:
    @pytest.mark.asyncio
    async def test_add_concatenates_messages_and_preserves_metadata(self, client):
        body = {
            "messages": [{"role": "user", "content": "we use pytest"}],
            "user_id": "host",
            "app_id": "A",
            "metadata": {"type": "decision", "file": "x.py"},
            "infer": False,
        }
        data = (await client.post("/v3/memories/add/", json=body)).json()
        assert data["status"] == "ok"
        assert data["event_id"] == "new-1"

        text, kwargs = client._fake.add_calls[0]
        assert "we use pytest" in text
        assert kwargs["project"] == "A"
        assert kwargs["infer"] is False
        assert kwargs["metadata"]["type"] == "decision"
        assert kwargs["metadata"]["file"] == "x.py"
        assert kwargs["metadata"]["project"] == "A"  # scoping injected

    @pytest.mark.asyncio
    async def test_empty_payload_is_noop(self, client):
        data = (await client.post("/v3/memories/add/", json={"app_id": "A"})).json()
        assert data["status"] == "empty"
        assert client._fake.add_calls == []


class TestList:
    @pytest.mark.asyncio
    async def test_count_and_results_project_scoped(self, client):
        body = {"filters": _and({"app_id": "A"})}
        data = (await client.post("/v3/memories/?page=1&page_size=10", json=body)).json()
        assert data["count"] == 2
        assert {r["id"] for r in data["results"]} == {"a1", "a2"}
