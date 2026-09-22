from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.sarvam import SarvamLLM


@pytest.fixture
def sarvam_llm():
    config = BaseLlmConfig(model="sarvam-m", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
    return SarvamLLM(config)


def _mock_post(content="Hello there!"):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock_response


def test_generate_response_returns_content(sarvam_llm):
    with patch("mem0.llms.sarvam.requests.post", return_value=_mock_post("Hi!")) as mock_post:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]
        response = sarvam_llm.generate_response(messages)

    assert response == "Hi!"
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["model"] == "sarvam-m"
    assert sent_payload["messages"] == messages
    assert sent_payload["temperature"] == 0.7


def test_generate_response_forwards_extra_kwargs(sarvam_llm):
    """Per the LLMBase contract, extra provider-specific kwargs must be accepted and
    forwarded into the Sarvam request payload."""
    with patch("mem0.llms.sarvam.requests.post", return_value=_mock_post("Hi!")) as mock_post:
        messages = [{"role": "user", "content": "Hello"}]
        response = sarvam_llm.generate_response(messages, frequency_penalty=0.5)

    assert response == "Hi!"
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["frequency_penalty"] == 0.5
