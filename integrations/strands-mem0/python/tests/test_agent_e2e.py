"""End-to-end test: a real Strands Agent using Mem0MemoryStore via MemoryManager.

Exercises the full agent loop that the unit tests can't: the manager searches our
store and injects memories into a real model's prompt (recall), and its extraction
trigger routes raw turns to our ``add_messages`` (write). The mem0 backend is a
deterministic in-memory stub so the test is hermetic and free; live mem0 read/write
is covered elsewhere.

Opt-in (needs a real OpenAI-compatible model), skipped by default:

    STRANDS_MEM0_E2E=1 \
    OPENAI_API_KEY=... OPENAI_BASE_URL=https://.../v1 \
    STRANDS_MEM0_E2E_MODEL=gpt-4o-mini \
    pytest tests/test_agent_e2e.py -v
"""

import os

import pytest

_ENABLED = os.environ.get("STRANDS_MEM0_E2E") and os.environ.get("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(not _ENABLED, reason="set STRANDS_MEM0_E2E=1 + OPENAI_API_KEY to run")


class StubMem0:
    """Deterministic in-memory stand-in for a mem0 client (OSS shape)."""

    def __init__(self, seed=None):
        self.memories = [dict(m) for m in (seed or [])]
        self.search_calls = []
        self.add_calls = []

    def add(self, messages, **kwargs):
        self.add_calls.append((messages, kwargs))
        text = messages if isinstance(messages, str) else str(messages)
        self.memories.append({"id": f"m{len(self.memories)}", "memory": text})
        return {"results": [{"id": "x"}], "status": "SUCCEEDED"}

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return {"results": self.memories}


def _model():
    from strands.models.openai import OpenAIModel

    args = {"api_key": os.environ["OPENAI_API_KEY"]}
    if os.environ.get("OPENAI_BASE_URL"):
        args["base_url"] = os.environ["OPENAI_BASE_URL"]
    return OpenAIModel(
        client_args=args,
        model_id=os.environ.get("STRANDS_MEM0_E2E_MODEL", "gpt-4o-mini"),
        params={"max_completion_tokens": 4000},
    )


def test_agent_recalls_injected_memory():
    """search -> inject -> the model recalls a fact only present in memory."""
    from strands import Agent
    from strands.memory import MemoryManager

    from strands_mem0 import Mem0MemoryStore
    from strands_mem0.client import Mem0ServiceClient

    stub = StubMem0(seed=[
        {"id": "m0", "memory": "The user's internal project codename is Zephyr-9."},
        {"id": "m1", "memory": "The user deploys to production only on Fridays."},
    ])
    store = Mem0MemoryStore(user_id="e2e", client=Mem0ServiceClient(client=stub))
    agent = Agent(model=_model(), memory_manager=MemoryManager(stores=[store], injection=True))

    answer = str(agent("What is my internal project codename, and which day do I deploy to production?"))

    assert stub.search_calls, "MemoryManager never searched the store"
    assert "zephyr" in answer.lower(), f"codename not recalled: {answer!r}"
    assert "friday" in answer.lower(), f"deploy day not recalled: {answer!r}"


def test_agent_extraction_writes_via_add_messages():
    """A per-turn extraction trigger routes raw turns to our add_messages sink."""
    import asyncio
    import time

    from strands import Agent
    from strands.memory import ExtractionConfig, InvocationTrigger, MemoryManager

    from strands_mem0 import Mem0MemoryStore
    from strands_mem0.client import Mem0ServiceClient

    stub = StubMem0()
    store = Mem0MemoryStore(
        user_id="e2e-w",
        extraction=ExtractionConfig(trigger=InvocationTrigger()),
        client=Mem0ServiceClient(client=stub),
    )
    manager = MemoryManager(stores=[store], injection=True)
    agent = Agent(model=_model(), memory_manager=manager)

    agent("For the record: I adopted a cat named Mochi and switched my editor to Neovim.")

    # Extraction runs as a detached background task; drain it before asserting.
    for _ in range(20):
        pending = [t for t in getattr(manager, "_background_tasks", set()) if not t.done()]
        if not pending and stub.add_calls:
            break
        if pending:
            asyncio.get_event_loop().run_until_complete(asyncio.wait(pending, timeout=3))
        else:
            time.sleep(0.5)

    infer_writes = [c for c in stub.add_calls if c[1].get("infer") is True]
    assert infer_writes, "extraction never wrote via add_messages (infer=True)"
