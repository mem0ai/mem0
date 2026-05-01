import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

nemo_flow = pytest.importorskip("nemo_flow", reason="nemo-flow optional dependency is not installed")


def _load_example_module():
    path = Path(__file__).resolve().parents[1] / "examples" / "misc" / "nemo_flow_memory.py"
    spec = importlib.util.spec_from_file_location("nemo_flow_memory_example", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _has_scope_event(events, name: str, scope_category: str, category: str | None = None) -> bool:
    return any(
        isinstance(event, nemo_flow.ScopeEvent)
        and event.name == name
        and event.scope_category == scope_category
        and (category is None or event.category == category)
        for event in events
    )


@pytest.mark.asyncio
async def test_nemo_flow_memory_example_smoke():
    module = _load_example_module()
    events = []
    subscriber_name = f"mem0-nemo-flow-example-{uuid4().hex}"

    nemo_flow.subscribers.register(subscriber_name, lambda event: events.append(event))
    try:
        result = await module.run_demo()
    finally:
        nemo_flow.subscribers.deregister(subscriber_name)

    assert result["search_calls"] == [
        {
            "query": "What do I like to drink?",
            "kwargs": {
                "filters": {"user_id": "alex", "run_id": "demo-thread"},
                "top_k": 5,
                "threshold": 0.1,
            },
        }
    ]
    assert result["provider_requests"][0]["messages"][0] == {
        "role": "system",
        "content": "Relevant memories:\n- Alex prefers tea in the afternoon.",
    }
    assert result["add_calls"][0]["messages"] == [
        {"role": "user", "content": "What do I like to drink?"},
        {
            "role": "assistant",
            "content": "I found your memory: Relevant memories:\n- Alex prefers tea in the afternoon.",
        },
    ]
    assert _has_scope_event(events, "mem0.memory", "start", "custom")
    assert _has_scope_event(events, "mem0.memory", "end", "custom")
    assert _has_scope_event(events, "mem0.recall", "start", "retriever")
    assert _has_scope_event(events, "mem0.recall", "end", "retriever")
    assert _has_scope_event(events, "mem0.capture", "start", "custom")
    assert _has_scope_event(events, "mem0.capture", "end", "custom")
    assert _has_scope_event(events, "demo-llm", "start", "llm")
    assert _has_scope_event(events, "demo-llm", "end", "llm")
