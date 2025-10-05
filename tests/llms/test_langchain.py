from unittest.mock import Mock

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.langchain import LangchainLLM

# Add the import for BaseChatModel
try:
    from langchain.chat_models.base import BaseChatModel
except ImportError:
    from unittest.mock import MagicMock

    BaseChatModel = MagicMock


@pytest.fixture
def mock_langchain_model():
    """Mock a Langchain model for testing."""
    mock_model = Mock(spec=BaseChatModel)
    mock_model.invoke.return_value = Mock(content="This is a test response")
    return mock_model


def test_langchain_initialization(mock_langchain_model):
    """Test that LangchainLLM initializes correctly with a valid model."""
    # Create a config with the model instance directly
    config = BaseLlmConfig(model=mock_langchain_model, temperature=0.7, max_tokens=100, api_key="test-api-key")

    # Initialize the LangchainLLM
    llm = LangchainLLM(config)

    # Verify the model was correctly assigned
    assert llm.langchain_model == mock_langchain_model


def test_generate_response(mock_langchain_model):
    """Test that generate_response correctly processes messages and returns a response."""
    # Create a config with the model instance
    config = BaseLlmConfig(model=mock_langchain_model, temperature=0.7, max_tokens=100, api_key="test-api-key")

    # Initialize the LangchainLLM
    llm = LangchainLLM(config)

    # Create test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well! How can I help you?"},
        {"role": "user", "content": "Tell me a joke."},
    ]

    # Get response
    response = llm.generate_response(messages)

    # Verify the correct message format was passed to the model
    expected_langchain_messages = [
        ("system", "You are a helpful assistant."),
        ("human", "Hello, how are you?"),
        ("ai", "I'm doing well! How can I help you?"),
        ("human", "Tell me a joke."),
    ]

    mock_langchain_model.invoke.assert_called_once()
    # Extract the first argument of the first call
    actual_messages = mock_langchain_model.invoke.call_args[0][0]
    assert actual_messages == expected_langchain_messages
    assert response == "This is a test response"


def test_generate_response_with_tools(mock_langchain_model):
    config = BaseLlmConfig(model=mock_langchain_model, temperature=0.7, max_tokens=100, api_key="test-api-key")
    llm = LangchainLLM(config)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Add a new memory: Today is a sunny day."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_memory",
                "description": "Add a memory",
                "parameters": {
                    "type": "object",
                    "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
                    "required": ["data"],
                },
            },
        }
    ]

    mock_response = Mock()
    mock_response.content = "I've added the memory for you."

    mock_tool_call = Mock()
    mock_tool_call.__getitem__ = Mock(
        side_effect={"name": "add_memory", "args": {"data": "Today is a sunny day."}}.__getitem__
    )

    mock_response.tool_calls = [mock_tool_call]
    mock_langchain_model.invoke.return_value = mock_response
    mock_langchain_model.bind_tools.return_value = mock_langchain_model

    response = llm.generate_response(messages, tools=tools)

    mock_langchain_model.invoke.assert_called_once()

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_invalid_model():
    """Test that LangchainLLM raises an error with an invalid model."""
    config = BaseLlmConfig(model="not-a-valid-model-instance", temperature=0.7, max_tokens=100, api_key="test-api-key")

    with pytest.raises(ValueError, match="`model` must be an instance of BaseChatModel"):
        LangchainLLM(config)


def test_missing_model():
    """Test that LangchainLLM raises an error when model is None."""
    config = BaseLlmConfig(model=None, temperature=0.7, max_tokens=100, api_key="test-api-key")

    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainLLM(config)
