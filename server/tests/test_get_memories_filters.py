"""Regression tests for filter building in GET /memories (get_all_memories)."""

import main
from main import get_all_memories


class _StubMemory:
    def __init__(self):
        self.calls = []

    def get_all(self, **params):
        self.calls.append(params)
        return {"results": []}


def test_empty_string_ids_are_not_forwarded_as_filters(monkeypatch):
    # A real user_id plus empty-string agent_id/run_id (e.g. `?agent_id=&run_id=`).
    # The empty strings must be dropped, consistent with the `any([...])` guard
    # above, instead of being passed through as real (empty) filter values.
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

    assert stub.calls, "get_all should have been called"
    assert stub.calls[0]["filters"] == {"user_id": "alice"}
