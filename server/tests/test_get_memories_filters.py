"""Regression tests for entity-id filter scoping in server/main.py.

Empty-string entity ids (e.g. `?agent_id=`) must be dropped when building the
downstream filter/params, consistent with the `any([...])` "list all" / "id
required" guards. Otherwise they are forwarded as real (empty) filter values
and silently over-scope the query. Covers GET /memories, /search, and
DELETE /memories, which all shared the same `is not None` pattern.
"""

import main
from main import SearchRequest, delete_all_memories, get_all_memories, search_memories


class _StubMemory:
    def __init__(self):
        self.get_all_calls = []
        self.search_calls = []
        self.delete_all_calls = []

    def get_all(self, **params):
        self.get_all_calls.append(params)
        return {"results": []}

    def search(self, query, filters=None, **params):
        self.search_calls.append(filters)
        return {"results": []}

    def delete_all(self, **params):
        self.delete_all_calls.append(params)


def test_get_all_drops_empty_string_ids(monkeypatch):
    stub = _StubMemory()
    monkeypatch.setattr(main, "get_memory_instance", lambda: stub)

    get_all_memories(
        request=None,
        user_id="alice",
        run_id="",
        agent_id="",
        top_k=None,
        show_expired=False,
        _auth=None,
    )

    assert stub.get_all_calls, "get_all should have been called"
    assert stub.get_all_calls[0]["filters"] == {"user_id": "alice"}


def test_search_drops_empty_string_ids(monkeypatch):
    stub = _StubMemory()
    monkeypatch.setattr(main, "get_memory_instance", lambda: stub)

    search_memories(
        SearchRequest(query="hi", user_id="alice", agent_id="", run_id=""),
        _auth=None,
    )

    # Only the real id ends up in the deprecated-param -> filters promotion.
    assert stub.search_calls == [{"user_id": "alice"}]


def test_delete_all_drops_empty_string_ids(monkeypatch):
    stub = _StubMemory()
    monkeypatch.setattr(main, "get_memory_instance", lambda: stub)

    delete_all_memories(user_id="alice", run_id="", agent_id="", _auth=None)

    assert stub.delete_all_calls == [{"user_id": "alice"}]
