import sys
from types import SimpleNamespace

import pytest

from mem0.integrations import nemo_flow


class FakeLLMRequest:
    def __init__(self, headers, content):
        self.headers = dict(headers)
        self.content = dict(content)


class FakeInterceptors:
    def __init__(self):
        self.registered = {}
        self.deregistered = []

    def register_llm_execution(self, name, priority, callback):
        self.registered[name] = {"priority": priority, "callback": callback}

    def deregister_llm_execution(self, name):
        self.deregistered.append(name)
        return self.registered.pop(name, None) is not None


class FakeScope:
    def __init__(self):
        self.handle = None
        self.stack = []
        self.pushed = []
        self.popped = []

    def get_handle(self):
        return self.handle

    def push(self, name, scope_type, *, input=None, metadata=None, **kwargs):
        handle = SimpleNamespace(name=name, scope_type=scope_type, input=input, metadata=metadata)
        self.stack.append(handle)
        self.handle = handle
        self.pushed.append(
            {
                "name": name,
                "scope_type": scope_type,
                "input": input,
                "metadata": metadata,
                "handle": handle,
            }
        )
        return handle

    def pop(self, handle, *, output=None):
        self.popped.append({"name": handle.name, "output": output, "handle": handle})
        if self.stack and self.stack[-1] is handle:
            self.stack.pop()
        elif handle in self.stack:
            self.stack.remove(handle)
        self.handle = self.stack[-1] if self.stack else None


class HostedMemory:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    def search(self, query, **kwargs):
        self.search_calls.append({"query": query, "kwargs": kwargs})
        return {"results": [{"memory": "User prefers tea."}]}

    def add(self, messages, **kwargs):
        self.add_calls.append({"messages": messages, "kwargs": kwargs})
        return {"results": [{"memory": "User prefers tea.", "event": "ADD"}]}


class LocalMemory:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    def search(self, query, *, filters=None, top_k=20, threshold=0.1):
        self.search_calls.append(
            {
                "query": query,
                "kwargs": {"filters": filters, "top_k": top_k, "threshold": threshold},
            }
        )
        return {"results": [{"memory": "User prefers tea."}]}

    def add(self, messages, *, user_id=None, agent_id=None, run_id=None, metadata=None, infer=True):
        self.add_calls.append(
            {
                "messages": messages,
                "kwargs": {
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "run_id": run_id,
                    "metadata": metadata,
                    "infer": infer,
                },
            }
        )
        return {"results": [{"memory": "User prefers tea.", "event": "ADD"}]}


@pytest.fixture
def fake_nemo_flow(monkeypatch):
    intercepts = FakeInterceptors()
    scope = FakeScope()
    module = SimpleNamespace(
        LLMRequest=FakeLLMRequest,
        Json=dict,
        ScopeType=SimpleNamespace(Agent="agent", Retriever="retriever", Custom="custom"),
        intercepts=intercepts,
        scope=scope,
        get_scope_stack=lambda: SimpleNamespace(),
    )
    monkeypatch.setitem(sys.modules, "nemo_flow", module)
    return module


def test_install_registers_and_uninstalls_execution_intercept(fake_nemo_flow):
    memory = HostedMemory()

    handle = nemo_flow.install(memory, name="mem0.test", priority=12)

    assert handle.active is True
    assert fake_nemo_flow.intercepts.registered["mem0.test"]["priority"] == 12
    assert fake_nemo_flow.intercepts.registered["mem0.test"]["callback"] is handle.intercept
    assert handle.uninstall() is True
    assert handle.active is False
    assert handle.uninstall() is False
    assert fake_nemo_flow.intercepts.deregistered == ["mem0.test"]


@pytest.mark.asyncio
async def test_context_identity_recalls_and_captures_with_hosted_memory(fake_nemo_flow):
    memory = HostedMemory()
    nemo_flow.install(memory, name="mem0.context")
    intercept = fake_nemo_flow.intercepts.registered["mem0.context"]["callback"]
    seen_requests = []
    request = fake_nemo_flow.LLMRequest(
        {"x-trace": "abc"},
        {
            "model": "test-model",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "What should I drink?"},
            ],
        },
    )

    async def next_call(next_request):
        seen_requests.append(next_request)
        return {"choices": [{"message": {"content": "Drink tea."}}]}

    with nemo_flow.memory_scope(user_id="user-1", thread_id="thread-1"):
        response = await intercept("gpt-test", request, next_call)

    assert response == {"choices": [{"message": {"content": "Drink tea."}}]}
    assert len(seen_requests) == 1
    assert isinstance(seen_requests[0], FakeLLMRequest)
    assert seen_requests[0] is not request
    assert seen_requests[0].headers == {"x-trace": "abc"}

    messages = seen_requests[0].content["messages"]
    assert [message["role"] for message in messages] == ["system", "system", "user"]
    assert messages[1]["content"] == "Relevant memories:\n- User prefers tea."

    assert memory.search_calls == [
        {
            "query": "What should I drink?",
            "kwargs": {
                "filters": {"user_id": "user-1", "run_id": "thread-1"},
                "top_k": 5,
                "threshold": 0.1,
            },
        }
    ]
    assert memory.add_calls == [
        {
            "messages": [
                {"role": "user", "content": "What should I drink?"},
                {"role": "assistant", "content": "Drink tea."},
            ],
            "kwargs": {
                "user_id": "user-1",
                "run_id": "thread-1",
                "metadata": {"user_id": "user-1", "run_id": "thread-1"},
                "infer": True,
            },
        }
    ]
    assert [
        {
            "name": item["name"],
            "scope_type": item["scope_type"],
            "input": item["input"],
            "metadata": item["metadata"],
        }
        for item in fake_nemo_flow.scope.pushed
    ] == [
        {
            "name": "mem0.memory",
            "scope_type": "custom",
            "input": None,
            "metadata": {"integration": "mem0", "mem0": {"user_id": "user-1", "run_id": "thread-1"}},
        },
        {
            "name": "mem0.recall",
            "scope_type": "retriever",
            "input": {
                "query_length": len("What should I drink?"),
                "top_k": 5,
                "threshold": 0.1,
            },
            "metadata": {
                "integration": "mem0",
                "filter_keys": ["run_id", "user_id"],
                "has_user_id": True,
                "has_agent_id": False,
                "has_run_id": True,
            },
        },
        {
            "name": "mem0.capture",
            "scope_type": "custom",
            "input": {"message_count": 2, "infer": True},
            "metadata": {
                "integration": "mem0",
                "filter_keys": ["run_id", "user_id"],
                "has_user_id": True,
                "has_agent_id": False,
                "has_run_id": True,
            },
        },
    ]
    assert [{"name": item["name"], "output": item["output"]} for item in fake_nemo_flow.scope.popped] == [
        {"name": "mem0.recall", "output": {"result_count": 1, "injected": True}},
        {"name": "mem0.capture", "output": {"message_count": 2, "stored": True}},
        {"name": "mem0.memory", "output": None},
    ]


@pytest.mark.asyncio
async def test_scope_metadata_can_supply_mem0_identity(fake_nemo_flow):
    memory = HostedMemory()
    nemo_flow.install(memory, name="mem0.scope", top_k=2, threshold=None)
    intercept = fake_nemo_flow.intercepts.registered["mem0.scope"]["callback"]
    fake_nemo_flow.scope.handle = SimpleNamespace(
        metadata={"mem0": {"user_id": "scope-user", "filters": {"tenant_id": "tenant-1"}}}
    )
    request = fake_nemo_flow.LLMRequest({}, {"messages": [{"role": "user", "content": "Remember this?"}]})

    async def next_call(next_request):
        return {"content": "I will remember."}

    await intercept("gpt-test", request, next_call)

    assert memory.search_calls[0]["kwargs"] == {
        "filters": {"tenant_id": "tenant-1", "user_id": "scope-user"},
        "top_k": 2,
    }
    assert memory.add_calls[0]["kwargs"]["user_id"] == "scope-user"
    assert memory.add_calls[0]["kwargs"]["metadata"] == {"tenant_id": "tenant-1", "user_id": "scope-user"}


@pytest.mark.asyncio
async def test_no_identity_skips_mem0_and_calls_next_with_original_request(fake_nemo_flow):
    memory = HostedMemory()
    nemo_flow.install(memory, name="mem0.no_identity")
    intercept = fake_nemo_flow.intercepts.registered["mem0.no_identity"]["callback"]
    request = fake_nemo_flow.LLMRequest({}, {"messages": [{"role": "user", "content": "Hi"}]})
    seen_requests = []

    async def next_call(next_request):
        seen_requests.append(next_request)
        return {"content": "Hello"}

    assert await intercept("gpt-test", request, next_call) == {"content": "Hello"}
    assert seen_requests == [request]
    assert memory.search_calls == []
    assert memory.add_calls == []
    assert fake_nemo_flow.scope.pushed == []
    assert fake_nemo_flow.scope.popped == []


@pytest.mark.asyncio
async def test_local_memory_capture_uses_top_level_session_ids(fake_nemo_flow):
    memory = LocalMemory()
    nemo_flow.install(memory, name="mem0.local")
    intercept = fake_nemo_flow.intercepts.registered["mem0.local"]["callback"]
    request = fake_nemo_flow.LLMRequest({}, {"messages": [{"role": "user", "content": "What should I drink?"}]})

    async def next_call(next_request):
        return {"content": "Drink tea."}

    with nemo_flow.memory_scope(user_id="local-user", agent_id="agent-1"):
        await intercept("gpt-test", request, next_call)

    assert memory.search_calls[0]["kwargs"]["filters"] == {"user_id": "local-user", "agent_id": "agent-1"}
    assert memory.add_calls[0]["kwargs"] == {
        "user_id": "local-user",
        "agent_id": "agent-1",
        "run_id": None,
        "metadata": {"user_id": "local-user", "agent_id": "agent-1"},
        "infer": True,
    }


def test_legacy_names_remain_available():
    assert nemo_flow.memory_context is nemo_flow.memory_scope
    assert nemo_flow.mem0_context is nemo_flow.memory_scope
    assert nemo_flow.install_mem0 is nemo_flow.install


def test_thread_id_conflict_is_rejected():
    with pytest.raises(ValueError, match="run_id and thread_id"):
        with nemo_flow.memory_scope(user_id="user-1", run_id="run-1", thread_id="thread-1"):
            pass
