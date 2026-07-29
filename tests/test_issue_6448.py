"""Regression test for issue #6448: reranking must receive a candidate pool."""

from unittest.mock import MagicMock

from mem0 import Memory
from mem0.memory import main as memory_main


def test_issue_6448(monkeypatch):
    """A reranker can promote a relevant result ranked below the requested limit."""
    first_stage_candidates = [
        {"id": f"candidate-{index}", "memory": f"less relevant memory {index}"}
        for index in range(1, 7)
    ]
    relevant_memory = {"id": "refund-policy", "memory": "The refund policy allows returns within 30 days."}
    first_stage_candidates.append(relevant_memory)

    memory = object.__new__(Memory)
    memory.api_version = "v1.1"
    memory._search_vector_store = MagicMock(
        side_effect=lambda query, filters, limit, threshold, **kwargs: first_stage_candidates[:limit]
    )

    reranker = MagicMock()

    def rerank(query, candidates, top_k):
        assert relevant_memory in candidates
        return [relevant_memory, *[candidate for candidate in candidates if candidate != relevant_memory]][:top_k]

    reranker.rerank.side_effect = rerank
    memory.reranker = reranker

    monkeypatch.setattr(memory_main, "capture_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory_main, "display_first_run_notice", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory_main, "display_scale_threshold_notice", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", lambda *args, **kwargs: None)

    result = memory.search(
        "refund policy",
        filters={"user_id": "u1"},
        top_k=5,
        rerank=True,
    )

    assert result["results"][0] == relevant_memory
    assert len(result["results"]) == 5
