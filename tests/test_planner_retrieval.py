from unittest.mock import AsyncMock, Mock, patch

import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.utils.planner_retrieval import build_planner_query, rerank_plan_memories


def test_build_planner_query_includes_planning_context():
    query = build_planner_query(
        user_goal="Prepare a pull request for a memory-agent project",
        plan=["Inspect contribution rules", "Implement a minimal example", "Add tests"],
        current_step="Implement a minimal example",
        tools=["github", "pytest", "python"],
        previous_failures=["Avoid changing core APIs before maintainer confirmation"],
    )

    assert "User goal: Prepare a pull request for a memory-agent project" in query
    assert "1. Inspect contribution rules" in query
    assert "Current step: Implement a minimal example" in query
    assert "Available tools: github, pytest, python" in query
    assert "- Avoid changing core APIs before maintainer confirmation" in query


def test_build_planner_query_requires_user_goal():
    with pytest.raises(ValueError, match="user_goal"):
        build_planner_query("   ")


def test_rerank_plan_memories_prioritizes_current_step_and_tools():
    memories = [
        {"memory": "General preference: write concise summaries.", "score": 0.9},
        {"memory": "When implementing examples, add pytest coverage before opening a PR.", "score": 0.2},
        {"memory": "Use GitHub labels when triaging bugs.", "score": 0.3},
    ]

    result = rerank_plan_memories(
        memories,
        user_goal="Prepare a pull request for a memory-agent project",
        current_step="Implement example tests",
        tools=["pytest"],
        limit=2,
    )

    assert result[0]["memory"] == "When implementing examples, add pytest coverage before opening a PR."
    assert len(result) == 2


def test_search_for_plan_builds_query_and_reranks_candidates():
    with patch.object(Memory, "__init__", return_value=None):
        memory = Memory()
    memory.search = Mock(
        return_value={
            "results": [
                {"memory": "General preference: write concise summaries.", "score": 0.9},
                {"memory": "When implementing examples, add pytest coverage before opening a PR.", "score": 0.2},
            ]
        }
    )

    result = memory.search_for_plan(
        user_goal="Prepare a pull request for a memory-agent project",
        plan=["Inspect contribution rules", "Implement a minimal example", "Add tests"],
        current_step="Implement a minimal example",
        tools=["pytest"],
        filters={"user_id": "u1"},
        limit=1,
    )

    called_query = memory.search.call_args.args[0]
    called_kwargs = memory.search.call_args.kwargs
    assert "Current step: Implement a minimal example" in called_query
    assert called_kwargs["top_k"] == 4
    assert called_kwargs["filters"] == {"user_id": "u1"}
    assert result["results"] == [
        {"memory": "When implementing examples, add pytest coverage before opening a PR.", "score": 0.2}
    ]


@pytest.mark.asyncio
async def test_async_search_for_plan_builds_query_and_reranks_candidates():
    with patch.object(AsyncMemory, "__init__", return_value=None):
        memory = AsyncMemory()
    memory.search = AsyncMock(
        return_value={
            "results": [
                {"memory": "General preference: write concise summaries.", "score": 0.9},
                {"memory": "When implementing examples, add pytest coverage before opening a PR.", "score": 0.2},
            ]
        }
    )

    result = await memory.search_for_plan(
        user_goal="Prepare a pull request for a memory-agent project",
        current_step="Implement a minimal example",
        tools=["pytest"],
        filters={"user_id": "u1"},
        limit=1,
    )

    called_query = memory.search.call_args.args[0]
    called_kwargs = memory.search.call_args.kwargs
    assert "Current step: Implement a minimal example" in called_query
    assert called_kwargs["top_k"] == 4
    assert called_kwargs["filters"] == {"user_id": "u1"}
    assert result["results"] == [
        {"memory": "When implementing examples, add pytest coverage before opening a PR.", "score": 0.2}
    ]
