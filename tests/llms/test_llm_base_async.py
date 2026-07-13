import asyncio

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class EchoLLM(LLMBase):
    def __init__(self):
        super().__init__(BaseLlmConfig(model="demo-model"))
        self.calls = []

    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        self.calls.append((messages, tools, tool_choice, kwargs))
        return {"messages": messages, "tools": tools, "tool_choice": tool_choice, "kwargs": kwargs}


class BoomLLM(LLMBase):
    def __init__(self):
        super().__init__(BaseLlmConfig(model="demo-model"))

    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        raise RuntimeError("sync boom")


def test_agenerate_response_falls_back_to_sync_provider():
    llm = EchoLLM()
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"type": "function"}]

    result = asyncio.run(
        llm.agenerate_response(
            messages,
            tools=tools,
            tool_choice="required",
            response_format={"type": "json_object"},
            retry=1,
        )
    )

    assert result["messages"] == messages
    assert result["tools"] == tools
    assert result["tool_choice"] == "required"
    assert result["kwargs"] == {"response_format": {"type": "json_object"}, "retry": 1}
    assert llm.calls == [(messages, tools, "required", {"response_format": {"type": "json_object"}, "retry": 1})]


def test_agenerate_response_propagates_sync_provider_errors():
    with pytest.raises(RuntimeError, match="sync boom"):
        asyncio.run(BoomLLM().agenerate_response([{"role": "user", "content": "hello"}]))
