import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.siliconflow import SiliconFlowLLM


@patch("mem0.llms.siliconflow.requests.post")
def test_generate_response_without_tools(mock_post, monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    config = BaseLlmConfig(model="Qwen/Qwen2.5-7B-Instruct", temperature=0.3, max_tokens=64, top_p=1.0)
    llm = SiliconFlowLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello SiliconFlow"},
    ]

    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {"choices": [{"message": {"content": "Hello back!"}}]},
    )

    response = llm.generate_response(messages)

    mock_post.assert_called_once()
    called_payload = mock_post.call_args.kwargs["json"]
    assert called_payload["model"] == config.model
    assert called_payload["messages"][1]["content"] == "Hello SiliconFlow"
    assert response == "Hello back!"


@patch("mem0.llms.siliconflow.requests.post")
def test_generate_response_with_tools(mock_post, monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    config = BaseLlmConfig(model="Qwen/Qwen2.5-7B-Instruct", temperature=0.3, max_tokens=64, top_p=1.0)
    llm = SiliconFlowLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Call a tool"},
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Echo input",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
        }
    ]

    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "choices": [
                {
                    "message": {
                        "content": "Tool called.",
                        "tool_calls": [{"function": {"name": "echo", "arguments": '{"text":"hi"}'}}],
                    }
                }
            ]
        },
    )

    response = llm.generate_response(messages, tools=tools)

    mock_post.assert_called_once()
    called_payload = mock_post.call_args.kwargs["json"]
    assert called_payload["tools"] == tools
    assert response["content"] == "Tool called."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "echo"
    assert response["tool_calls"][0]["arguments"]["text"] == "hi"


@patch("mem0.llms.siliconflow.requests.post")
def test_generate_response_error(mock_post, monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    config = BaseLlmConfig(model="Qwen/Qwen2.5-7B-Instruct", temperature=0.3, max_tokens=64, top_p=1.0)
    llm = SiliconFlowLLM(config)

    mock_post.return_value = Mock(status_code=500, text="Internal Error")

    import pytest

    with pytest.raises(RuntimeError):
        llm.generate_response([{"role": "user", "content": "Hi"}])


# ------------------------- LIVE INTEGRATION (optional) ------------------------- #
@pytest.mark.skipif(not os.getenv("SILICONFLOW_API_KEY"), reason="No SiliconFlow API key set")
def test_siliconflow_live_basic():
    """Live call to SiliconFlow API (non-mocked). Skipped if no key.
    Keeps tokens low to control cost.
    Set SILICONFLOW_MODEL to override model name.
    """
    model = os.getenv("SILICONFLOW_MODEL", "Qwen/QwQ-32B")
    cfg = BaseLlmConfig(model=model, temperature=0.2, max_tokens=64, top_p=0.9)
    llm = SiliconFlowLLM(cfg)

    prompt = "In one concise sentence, say hello from SiliconFlow integration test."
    resp = llm.generate_response([{"role": "user", "content": prompt}])

    assert isinstance(resp, str)
    assert resp.strip() and resp.strip() != prompt
