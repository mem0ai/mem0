from unittest.mock import Mock, patch

import pytest

from mem0.utils.factory import LlmFactory
from mem0.configs.llms.base import BaseLlmConfig


@pytest.fixture
def mock_litellm():
    with patch("mem0.llms.litellm.litellm") as mock_litellm:
        yield mock_litellm


@pytest.mark.parametrize(
    "model",
    [
        # Current MiniMax model family (from official docs)
        "minimax/MiniMax-M2.5",
        "minimax/MiniMax-M2.5-highspeed",
        "minimax/MiniMax-M2.1",
        "minimax/MiniMax-M2.1-highspeed",
        "minimax/MiniMax-M2",
        "minimax/M2-her",
        # Backward-compatible older naming seen in community examples
        "minimax/abab6.5s-chat",
    ],
)
def test_minimax_model_passthrough(mock_litellm, model):
    mock_litellm.supports_function_calling.return_value = True

    llm = LlmFactory.create("minimax", BaseLlmConfig(model=model, temperature=0.2, max_tokens=64, top_p=0.9))
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_litellm.completion.return_value = mock_response

    resp = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model=model, messages=messages, temperature=0.2, max_tokens=64, top_p=0.9
    )
    assert resp == "ok"

