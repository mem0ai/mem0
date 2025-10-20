
import pytest
from unittest.mock import MagicMock, patch

from mem0.llms.lm_studio import LMStudioLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.lm_studio.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response(mock_openai_client):
    # Mock the response from the API
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Hello, world!"
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm = LMStudioLLM()
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.generate_response(messages)

    assert response == "Hello, world!"
    mock_openai_client.chat.completions.create.assert_called_once_with(
        model='gpt-4',
        messages=[{'role': 'user', 'content': 'Hello'}],
        temperature=0.1,
        max_tokens=4000,
        top_p=1.0,
        stream=False
    )
