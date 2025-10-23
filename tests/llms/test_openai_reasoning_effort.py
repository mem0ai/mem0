"""
Test reasoning_effort parameter for OpenAI reasoning models (o1, o3, gpt-5).
This test verifies that the reasoning_effort parameter is properly passed to the API.
"""
import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_reasoning_effort_parameter_with_o1_model(mock_openai_client):
    """Test that reasoning_effort is passed correctly for o1 model."""
    config = OpenAIConfig(
        model="o1-preview",
        api_key="test-api-key",
        reasoning_effort="high"
    )
    llm = OpenAILLM(config)
    
    messages = [
        {"role": "user", "content": "Solve this complex problem: What is 2+2?"}
    ]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="The answer is 4"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Call generate_response
    response = llm.generate_response(messages)
    
    # Verify the API was called with reasoning_effort
    mock_openai_client.chat.completions.create.assert_called_once()
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    
    assert "reasoning_effort" in call_args
    assert call_args["reasoning_effort"] == "high"
    assert call_args["model"] == "o1-preview"
    assert call_args["messages"] == messages
    assert response == "The answer is 4"


def test_reasoning_effort_parameter_with_o3_mini(mock_openai_client):
    """Test that reasoning_effort is passed correctly for o3-mini model."""
    config = OpenAIConfig(
        model="o3-mini",
        api_key="test-api-key",
        reasoning_effort="medium"
    )
    llm = OpenAILLM(config)
    
    messages = [
        {"role": "user", "content": "Explain quantum computing"}
    ]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Quantum computing explanation..."))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Call generate_response
    response = llm.generate_response(messages)
    
    # Verify the API was called with reasoning_effort
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    
    assert "reasoning_effort" in call_args
    assert call_args["reasoning_effort"] == "medium"
    assert call_args["model"] == "o3-mini"


def test_reasoning_effort_parameter_low(mock_openai_client):
    """Test that reasoning_effort='low' works correctly."""
    config = OpenAIConfig(
        model="o1",
        api_key="test-api-key",
        reasoning_effort="low"
    )
    llm = OpenAILLM(config)
    
    messages = [{"role": "user", "content": "Simple question"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Simple answer"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    response = llm.generate_response(messages)
    
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    assert call_args["reasoning_effort"] == "low"


def test_reasoning_effort_not_passed_for_regular_models(mock_openai_client):
    """Test that reasoning_effort is NOT passed for regular GPT models."""
    config = OpenAIConfig(
        model="gpt-4",
        api_key="test-api-key",
        reasoning_effort="high"  # This should be ignored for non-reasoning models
    )
    llm = OpenAILLM(config)
    
    messages = [{"role": "user", "content": "Hello"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi there"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    response = llm.generate_response(messages)
    
    # Verify reasoning_effort is NOT in the API call
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    
    assert "reasoning_effort" not in call_args
    # Regular model parameters should be present
    assert "temperature" in call_args
    assert "max_tokens" in call_args
    assert "top_p" in call_args


def test_reasoning_effort_none_not_passed(mock_openai_client):
    """Test that reasoning_effort is not passed when None."""
    config = OpenAIConfig(
        model="o1-preview",
        api_key="test-api-key",
        reasoning_effort=None
    )
    llm = OpenAILLM(config)
    
    messages = [{"role": "user", "content": "Test"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    response = llm.generate_response(messages)
    
    # Verify reasoning_effort is NOT in the API call when None
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    assert "reasoning_effort" not in call_args


def test_reasoning_effort_validation_invalid_value():
    """Test that invalid reasoning_effort values raise ValueError."""
    with pytest.raises(ValueError, match="reasoning_effort must be one of"):
        config = OpenAIConfig(
            model="o1-preview",
            api_key="test-api-key",
            reasoning_effort="invalid"  # Invalid value
        )
        llm = OpenAILLM(config)


def test_reasoning_effort_validation_valid_values():
    """Test that all valid reasoning_effort values are accepted."""
    valid_values = ["low", "medium", "high"]
    
    for value in valid_values:
        config = OpenAIConfig(
            model="o1-preview",
            api_key="test-api-key",
            reasoning_effort=value
        )
        llm = OpenAILLM(config)
        assert llm.config.reasoning_effort == value


def test_reasoning_effort_with_gpt5_model(mock_openai_client):
    """Test that reasoning_effort works with GPT-5 models."""
    config = OpenAIConfig(
        model="gpt-5",
        api_key="test-api-key",
        reasoning_effort="high"
    )
    llm = OpenAILLM(config)
    
    messages = [{"role": "user", "content": "Test GPT-5"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="GPT-5 response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    response = llm.generate_response(messages)
    
    # Verify reasoning_effort is passed for GPT-5
    call_args = mock_openai_client.chat.completions.create.call_args[1]
    assert "reasoning_effort" in call_args
    assert call_args["reasoning_effort"] == "high"


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping live API test"
)
def test_reasoning_effort_live_api():
    """
    Live integration test with real OpenAI API.
    Requires OPENAI_API_KEY environment variable.
    
    To run this test:
    export OPENAI_API_KEY="your-api-key"
    pytest tests/llms/test_openai_reasoning_effort.py::test_reasoning_effort_live_api -v
    """
    config = OpenAIConfig(
        model="o1-mini",  # Using o1-mini as it's available
        reasoning_effort="low",
        # api_key will be picked up from environment
    )
    llm = OpenAILLM(config)
    
    messages = [
        {"role": "user", "content": "What is 5 + 3? Just give me the number."}
    ]
    
    try:
        response = llm.generate_response(messages)
        assert response is not None
        assert len(response) > 0
        print(f"✓ Live API test successful. Response: {response}")
    except Exception as e:
        pytest.fail(f"Live API test failed: {str(e)}")


if __name__ == "__main__":
    # For manual testing
    print("Running reasoning_effort tests...")
    pytest.main([__file__, "-v"])
