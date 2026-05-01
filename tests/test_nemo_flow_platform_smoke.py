import os
import uuid

import pytest


def _contains_text(response, expected: str) -> bool:
    expected = expected.lower()
    stack = [response]
    while stack:
        item = stack.pop()
        if isinstance(item, str) and expected in item.lower():
            return True
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def _best_effort_delete_user(client, user_id: str) -> None:
    try:
        client.delete_users(user_id=user_id)
    except Exception:
        pass


def _has_scope_event(events, nemo_flow, name: str, scope_category: str, category: str | None = None) -> bool:
    return any(
        isinstance(event, nemo_flow.ScopeEvent)
        and event.name == name
        and event.scope_category == scope_category
        and (category is None or event.category == category)
        for event in events
    )


@pytest.mark.asyncio
async def test_nemo_flow_platform_storage_smoke():
    if os.getenv("RUN_MEM0_NEMO_FLOW_PLATFORM_SMOKE") != "1":
        pytest.skip("set RUN_MEM0_NEMO_FLOW_PLATFORM_SMOKE=1 to run the real Mem0 Platform smoke")

    pytest.importorskip("nemo_flow", reason="nemo-flow optional dependency is not installed")

    import nemo_flow

    from mem0 import MemoryClient
    from mem0.integrations import nemo_flow as mem0_nemo_flow

    api_key = os.getenv("MEM0_API_KEY")
    if not api_key:
        pytest.skip("MEM0_API_KEY is required for the real Mem0 Platform smoke")

    user_id = f"nemo-flow-smoke-{uuid.uuid4().hex}"
    run_id = "storage-smoke"
    seed_memory = f"{user_id} prefers jasmine tea in the afternoon."
    write_marker = f"nemo-flow-write-{uuid.uuid4().hex}"
    filters = {"user_id": user_id, "run_id": run_id}
    client = MemoryClient(api_key=api_key)
    handle = None
    events = []
    subscriber_name = f"mem0-nemo-flow-platform-{uuid.uuid4().hex}"

    try:
        nemo_flow.subscribers.register(subscriber_name, lambda event: events.append(event))
        client.add(seed_memory, user_id=user_id, run_id=run_id, infer=False)
        seed_search = client.search("jasmine tea afternoon", filters=filters, top_k=5, threshold=0)
        assert _contains_text(seed_search, "jasmine tea")

        handle = mem0_nemo_flow.install(client, name=f"mem0.platform.{user_id}", infer=False, threshold=0)
        provider_requests = []

        async def demo_llm(request: nemo_flow.LLMRequest) -> dict:
            provider_requests.append(request.content)
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"I will remember this marker: {write_marker}",
                        }
                    }
                ]
            }

        request = nemo_flow.LLMRequest(
            {},
            {
                "model": "demo-model",
                "messages": [{"role": "user", "content": "What tea do I prefer?"}],
            },
        )
        with mem0_nemo_flow.memory_scope(user_id=user_id, run_id=run_id):
            await nemo_flow.llm.execute("demo-llm", request, demo_llm)

        assert _contains_text(provider_requests, "jasmine tea")

        write_search = client.search(write_marker, filters=filters, top_k=5, threshold=0)
        assert _contains_text(write_search, write_marker)

        assert _has_scope_event(events, nemo_flow, "mem0.memory", "start", "custom")
        assert _has_scope_event(events, nemo_flow, "mem0.memory", "end", "custom")
        assert _has_scope_event(events, nemo_flow, "mem0.recall", "start", "retriever")
        assert _has_scope_event(events, nemo_flow, "mem0.recall", "end", "retriever")
        assert _has_scope_event(events, nemo_flow, "mem0.capture", "start", "custom")
        assert _has_scope_event(events, nemo_flow, "mem0.capture", "end", "custom")
        assert _has_scope_event(events, nemo_flow, "demo-llm", "start", "llm")
        assert _has_scope_event(events, nemo_flow, "demo-llm", "end", "llm")
    finally:
        nemo_flow.subscribers.deregister(subscriber_name)
        if handle is not None:
            handle.uninstall()
        _best_effort_delete_user(client, user_id)
