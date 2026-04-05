import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


@pytest.fixture
def mock_openai_clients():
    with patch("mem0.llms.openai.OpenAI") as mock_openai, \
         patch("mem0.llms.openai.AsyncOpenAI") as mock_async_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_async_client = Mock()
        mock_async_openai.return_value = mock_async_client
        yield mock_client, mock_async_client


@pytest.mark.asyncio
async def test_agenerate_response_without_tools(mock_openai_clients):
    _, mock_async_client = mock_openai_clients
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    response = await llm.agenerate_response(messages)

    mock_async_client.chat.completions.create.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, store=False
    )
    assert response == "I'm doing well, thank you for asking!"


@pytest.mark.asyncio
async def test_agenerate_response_with_tools(mock_openai_clients):
    _, mock_async_client = mock_openai_clients
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)

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
    mock_message = Mock()
    mock_message.content = "I've added the memory for you."
    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "Today is a sunny day."}'
    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    response = await llm.agenerate_response(messages, tools=tools)

    mock_async_client.chat.completions.create.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0,
        tools=tools, tool_choice="auto", store=False
    )
    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


@pytest.mark.asyncio
async def test_agenerate_response_with_response_format(mock_openai_clients):
    _, mock_async_client = mock_openai_clients
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)

    messages = [{"role": "user", "content": "Return JSON"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    response = await llm.agenerate_response(messages, response_format={"type": "json_object"})

    call_kwargs = mock_async_client.chat.completions.create.call_args[1]
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert response == '{"key": "value"}'


@pytest.mark.asyncio
async def test_agenerate_uses_async_client_not_sync(mock_openai_clients):
    """Verify that agenerate_response uses async_client, not the sync client."""
    mock_sync_client, mock_async_client = mock_openai_clients
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)

    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_async_client.chat.completions.create = AsyncMock(return_value=mock_response)

    await llm.agenerate_response(messages)

    # Async client should be called
    mock_async_client.chat.completions.create.assert_called_once()
    # Sync client should NOT be called
    mock_sync_client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_async_client_initialized(mock_openai_clients):
    """Verify that both sync and async clients are initialized."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", api_key="test-key")
    llm = OpenAILLM(config)
    assert hasattr(llm, 'client')
    assert hasattr(llm, 'async_client')
