from unittest.mock import Mock, patch

import pytest
from google.generativeai import GenerationConfig
from google.generativeai.types import content_types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_client():
    with patch("mem0.llms.gemini.GenerativeModel") as mock_gemini:
        mock_client = Mock()
        mock_gemini.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(
        model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0
    )
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_part = Mock(text="I'm doing well, thank you for asking!")
    mock_content = Mock(parts=[mock_part])
    mock_message = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_message])
    mock_gemini_client.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    mock_gemini_client.generate_content.assert_called_once_with(
        contents=[
            {
                "parts": "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: You are a helpful assistant.",
                "role": "user",
            },
            {"parts": "Hello, how are you?", "role": "user"},
        ],
        generation_config=GenerationConfig(
            temperature=0.7, max_output_tokens=100, top_p=1.0
        ),
    )
    assert response == "I'm doing well, thank you for asking!"
