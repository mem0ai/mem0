from unittest.mock import Mock, patch
import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.langchain import LangchainLLM


@pytest.fixture
def mock_langchain_model():
    """Mock a Langchain model for testing."""
    with patch("langchain_openai.ChatOpenAI") as mock_chat_model:
        mock_model = Mock()
        mock_model.invoke.return_value = Mock(content="This is a test response")
        mock_chat_model.return_value = mock_model
        yield mock_model


def test_langchain_initialization():
    """Test that LangchainLLM initializes correctly with a valid provider."""
    with patch("langchain_openai.ChatOpenAI") as mock_chat_model:
        # Setup the mock model
        mock_model = Mock()
        mock_chat_model.return_value = mock_model
        
        # Create a config with OpenAI provider
        config = BaseLlmConfig(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=100,
            api_key="test-api-key",
            langchain_provider="OpenAI"
        )
        
        # Initialize the LangchainLLM
        llm = LangchainLLM(config)
        
        # Verify the model was initialized with correct parameters
        mock_chat_model.assert_called_once_with(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=100,
            api_key="test-api-key"
        )
        
        assert llm.langchain_model == mock_model


def test_generate_response(mock_langchain_model):
    """Test that generate_response correctly processes messages and returns a response."""
    # Create a config with OpenAI provider
    config = BaseLlmConfig(
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=100,
        api_key="test-api-key",
        langchain_provider="OpenAI"
    )
    
    # Initialize the LangchainLLM
    with patch("langchain_openai.ChatOpenAI", return_value=mock_langchain_model):
        llm = LangchainLLM(config)
        
        # Create test messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well! How can I help you?"},
            {"role": "user", "content": "Tell me a joke."}
        ]
        
        # Get response
        response = llm.generate_response(messages)
        
        # Verify the correct message format was passed to the model
        expected_langchain_messages = [
            ("system", "You are a helpful assistant."),
            ("human", "Hello, how are you?"),
            ("ai", "I'm doing well! How can I help you?"),
            ("human", "Tell me a joke.")
        ]
        
        mock_langchain_model.invoke.assert_called_once()
        # Extract the first argument of the first call
        actual_messages = mock_langchain_model.invoke.call_args[0][0]
        assert actual_messages == expected_langchain_messages
        assert response == "This is a test response"


def test_invalid_provider():
    """Test that LangchainLLM raises an error with an invalid provider."""
    config = BaseLlmConfig(
        model="test-model",
        temperature=0.7,
        max_tokens=100,
        api_key="test-api-key",
        langchain_provider="InvalidProvider"
    )
    
    with pytest.raises(ValueError, match="Invalid provider: InvalidProvider"):
        LangchainLLM(config)
