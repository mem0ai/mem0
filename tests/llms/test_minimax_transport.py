"""Exercise MiniMax requests through the real SDK serializers without network access."""

import importlib
import json

import pytest

from mem0.utils.factory import LlmFactory


@pytest.fixture
def capture_transport(monkeypatch):
    def capture(llm, response_body):
        requests = []

        def send(request, **kwargs):
            requests.append(request)
            # Match the SDK's HTTP implementation (httpx or httpx2).
            http = importlib.import_module(type(request).__module__.split(".")[0])
            return http.Response(200, request=request, json=response_body)

        monkeypatch.setattr(llm.client._client, "send", send)
        return requests

    return capture


@pytest.mark.parametrize("base_url", [None, "https://api.minimaxi.com/v1", "https://custom.example/v1"])
@pytest.mark.parametrize("model", [None, "MiniMax-M3.1-Flash", "MiniMax-M3", "MiniMax-M2.7", "saved-custom-model"])
def test_minimax_serialized_request(monkeypatch, capture_transport, base_url, model):
    monkeypatch.delenv("MINIMAX_API_BASE", raising=False)
    config = {"api_key": "test-key"}
    if model is not None:
        config["model"] = model
    if base_url is not None:
        config["minimax_base_url"] = base_url
    llm = LlmFactory.create("minimax", config)
    requests = capture_transport(
        llm,
        {
            "id": "chat-test",
            "object": "chat.completion",
            "created": 0,
            "model": model or "MiniMax-M3.1-Flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
        },
    )
    messages = [{"role": "system", "content": "Remember facts."}, {"role": "user", "content": "Hello"}]
    tools = [{"type": "function", "function": {"name": "remember", "parameters": {"type": "object"}}}]
    try:
        assert llm.generate_response(messages, tools=tools, response_format={"type": "json_object"}) == {
            "content": "OK",
            "tool_calls": [],
        }
    finally:
        llm.client.close()
    assert len(requests) == 1
    assert str(requests[0].url) == (base_url or "https://api.minimax.io/v1") + "/chat/completions"
    payload = json.loads(requests[0].content)
    assert payload["model"] == (model or "MiniMax-M3.1-Flash")
    assert payload["messages"] == messages
    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"
    assert payload["response_format"] == {"type": "json_object"}
    assert not {"thinking", "reasoning_effort", "reasoning_split", "service_tier"} & payload.keys()


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_minimax_preserves_effort_and_history(capture_transport, effort):
    messages = [
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}]},
        {
            "role": "assistant",
            "content": "Remembered",
            "reasoning_details": [{"type": "reasoning.text", "text": "Fact"}],
        },
        {"role": "user", "content": "Recall it"},
    ]
    llm = LlmFactory.create("minimax", {"api_key": "test-key"})
    requests = capture_transport(llm, {"choices": [{"message": {"content": "OK"}}]})
    try:
        assert (
            llm.generate_response(messages, reasoning_effort=effort, extra_body={"thinking": {"type": "adaptive"}})
            == "OK"
        )
    finally:
        llm.client.close()
    payload = json.loads(requests[0].content)
    assert payload["model"] == "MiniMax-M3.1-Flash"
    assert payload["messages"] == messages
    assert payload["reasoning_effort"] == effort
    assert payload["thinking"] == {"type": "adaptive"}


@pytest.mark.parametrize("host", ["api.minimax.io", "api.minimaxi.com"])
@pytest.mark.parametrize("model", ["MiniMax-M3.1-Flash", "MiniMax-M3"])
def test_minimax_anthropic_endpoint(capture_transport, host, model):
    pytest.importorskip("anthropic")
    llm = LlmFactory.create(
        "anthropic",
        {
            "api_key": "test-key",
            "model": model,
            "anthropic_base_url": f"https://{host}/anthropic",
        },
    )
    requests = capture_transport(
        llm,
        {
            "id": "msg-test",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": "OK"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    try:
        assert llm.generate_response([{"role": "user", "content": "Hello"}]) == "OK"
    finally:
        llm.client.close()
    assert str(requests[0].url) == f"https://{host}/anthropic/v1/messages"
    payload = json.loads(requests[0].content)
    assert payload["model"] == model
    assert payload["messages"] == [{"role": "user", "content": "Hello"}]
    assert "thinking" not in payload
    assert "service_tier" not in payload
