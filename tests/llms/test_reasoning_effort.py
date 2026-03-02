from unittest.mock import Mock, patch
import pytest
from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.llms.azure_openai import AzureOpenAILLM
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM

@pytest.fixture
def mock_azure_client():
    with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client

def test_azure_reasoning_effort(mock_azure_client):
    # Test with a reasoning model
    model = "o1-preview"
    effort = "high"
    config = AzureOpenAIConfig(model=model, reasoning_effort=effort)
    llm = AzureOpenAILLM(config)
    
    messages = [{"role": "user", "content": "Hi"}]
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hello", tool_calls=None))]
    mock_azure_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    # Check if reasoning_effort was passed
    args, kwargs = mock_azure_client.chat.completions.create.call_args
    assert kwargs["reasoning_effort"] == effort
    assert "temperature" not in kwargs # Reasoning models shouldn't have temperature

def test_openai_reasoning_effort(mock_openai_client):
    # Test with a reasoning model
    model = "o1"
    effort = "low"
    config = OpenAIConfig(model=model, reasoning_effort=effort)
    llm = OpenAILLM(config)
    
    messages = [{"role": "user", "content": "Hi"}]
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hello", tool_calls=None))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    # Check if reasoning_effort was passed
    args, kwargs = mock_openai_client.chat.completions.create.call_args
    assert kwargs["reasoning_effort"] == effort
    assert "temperature" not in kwargs
