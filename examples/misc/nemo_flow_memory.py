"""Run Mem0's NeMo Flow integration without external API keys.

This example uses a tiny in-memory object with the same `search` and `add`
methods that the integration expects from `MemoryClient`. Replace
`DemoMemoryClient` with `mem0.MemoryClient` in a real application.

Install the optional dependency before running:

    pip install "mem0ai[nemo_flow]"
    python examples/misc/nemo_flow_memory.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any


class DemoMemoryClient:
    """Small Mem0-compatible memory client for a no-credentials smoke run."""

    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.add_calls: list[dict[str, Any]] = []

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        self.search_calls.append({"query": query, "kwargs": kwargs})
        return {"results": [{"memory": "Alex prefers tea in the afternoon."}]}

    def add(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        self.add_calls.append({"messages": messages, "kwargs": kwargs})
        return {"results": [{"memory": messages[-1]["content"], "event": "ADD"}]}


async def run_demo() -> dict[str, Any]:
    from mem0.integrations import nemo_flow

    memory = DemoMemoryClient()
    handle = nemo_flow.install(memory, name="mem0.example.nemo_flow")
    provider_requests = []

    async def demo_llm(request: Any) -> dict[str, Any]:
        provider_requests.append(request.content)
        system_context = "\n".join(
            message["content"]
            for message in request.content["messages"]
            if message.get("role") == "system" and "Relevant memories:" in message.get("content", "")
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"I found your memory: {system_context}",
                    }
                }
            ]
        }

    try:
        with nemo_flow.memory_scope(user_id="alex", thread_id="demo-thread"):
            response = await _run_instrumented_framework_llm(
                "demo-llm",
                {
                    "model": "demo-model",
                    "messages": [{"role": "user", "content": "What do I like to drink?"}],
                },
                demo_llm,
            )
    finally:
        handle.uninstall()

    return {
        "response": response,
        "provider_requests": provider_requests,
        "search_calls": memory.search_calls,
        "add_calls": memory.add_calls,
    }


async def _run_instrumented_framework_llm(
    name: str,
    content: dict[str, Any],
    provider: Any,
) -> dict[str, Any]:
    """Simulate the LLM boundary that a patched framework would own."""

    import nemo_flow

    request = nemo_flow.LLMRequest({}, content)
    return await nemo_flow.llm.execute(name, request, provider)


def main() -> None:
    print(json.dumps(asyncio.run(run_demo()), indent=2))


if __name__ == "__main__":
    main()
