"""Exercise MiniMax requests through the real SDK serializers without network access."""

import json

import httpx
import pytest

from mem0.utils.factory import LlmFactory


@pytest.mark.parametrize("base_url", [None, "https://api.minimaxi.com/v1", "https://custom.example/v1"])
@pytest.mark.parametrize("model", [None, "MiniMax-M3.1-Flash", "MiniMax-M3", "MiniMax-M2.7", "saved-custom-model"])
def test_minimax_serialized_request(monkeypatch, base_url, model):
    monkeypatch.delenv("MINIMAX_API_BASE", raising=False)
    requests = []

    def send(client, request, **kwargs):
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": model or "MiniMax-M3.1-Flash",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
            },
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    config = {"api_key": "test-key"}
    if model is not None:
        config["model"] = model
    if base_url is not None:
        config["minimax_base_url"] = base_url
    llm = LlmFactory.create("minimax", config)
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
def test_minimax_preserves_effort_and_history(monkeypatch, effort):
    payloads = []

    def send(client, request, **kwargs):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(httpx.Client, "send", send)
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
    try:
        assert (
            llm.generate_response(messages, reasoning_effort=effort, extra_body={"thinking": {"type": "adaptive"}})
            == "OK"
        )
    finally:
        llm.client.close()
    assert payloads[0]["model"] == "MiniMax-M3.1-Flash"
    assert payloads[0]["messages"] == messages
    assert payloads[0]["reasoning_effort"] == effort
    assert payloads[0]["thinking"] == {"type": "adaptive"}


@pytest.mark.parametrize("host", ["api.minimax.io", "api.minimaxi.com"])
@pytest.mark.parametrize("model", ["MiniMax-M3.1-Flash", "MiniMax-M3"])
def test_minimax_anthropic_endpoint(monkeypatch, host, model):
    pytest.importorskip("anthropic")
    requests = []

    def send(client, request, **kwargs):
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "msg-test",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "OK"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    llm = LlmFactory.create(
        "anthropic", {"api_key": "test-key", "model": model, "anthropic_base_url": f"https://{host}/anthropic"}
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
