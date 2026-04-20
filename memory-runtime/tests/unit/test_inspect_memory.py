from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.inspect_memory import memory_units_to_report
from app.models.memory_unit import MemoryUnit


def _memory_unit(**overrides) -> MemoryUnit:
    now = datetime.now(timezone.utc)
    base = {
        "id": "memory-1",
        "namespace_id": "ns-1",
        "agent_id": "agent-1",
        "primary_space_id": "space-1",
        "kind": "decision",
        "scope": "long-term",
        "content": "Keep Postgres for memory-runtime.",
        "summary": "Keep Postgres for memory-runtime.",
        "importance_score": 0.9,
        "confidence_score": 0.8,
        "freshness_score": 0.7,
        "durability_score": 0.8,
        "access_count": 2,
        "last_accessed_at": now,
        "status": "active",
        "expires_at": None,
        "created_from_episode_id": None,
        "supersedes_memory_id": None,
        "merge_key": "merge-key",
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return MemoryUnit(**base)


def test_memory_units_to_report_includes_debugging_fields() -> None:
    unit = _memory_unit(status="superseded", supersedes_memory_id="memory-0")
    report = memory_units_to_report([unit])

    assert report[0]["status"] == "superseded"
    assert report[0]["supersedes_memory_id"] == "memory-0"
    assert report[0]["summary"] == "Keep Postgres for memory-runtime."


def test_explain_recall_formats_selection_explanations() -> None:
    payload = {
        "brief": {"prior_decisions": ["Keep Postgres."]},
        "trace": {
            "candidate_count": 4,
            "selected_count": 1,
            "selected_space_types": ["project-space"],
            "selection_explanations": [
                {
                    "episode_id": "episode-1",
                    "space_type": "project-space",
                    "slot": "prior_decisions",
                    "decisive_signal": "project_infrastructure",
                    "why": "was selected as a prior decision because it matched the current project setup",
                }
            ],
        },
    }

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return _Response()

    with patch("app.inspect_memory.httpx.Client", _Client):
        from app.inspect_memory import explain_recall

        report = explain_recall(
            base_url="http://127.0.0.1:8080",
            namespace_id="ns-1",
            agent_id="agent-1",
            session_id="session-1",
            query="What matters?",
            context_budget_tokens=800,
        )

    assert report["trace_summary"]["selected_count"] == 1
    assert report["selection_explanations"][0]["slot"] == "prior_decisions"
