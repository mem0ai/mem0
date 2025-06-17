import pytest
import json
from unittest.mock import AsyncMock, patch

# Adjust the import path to match your project structure
from openmemory.api.app.mcp_server import (
    get_original_tools_schema,
    get_chatgpt_tools_schema,
    handle_chatgpt_search,
    handle_chatgpt_fetch,
)

# --- Test Schema Generation ---

def test_get_original_tools_schema():
    """
    Tests that the original schema for standard clients (like the Playground)
    is returned correctly and uses 'inputSchema'.
    """
    schema = get_original_tools_schema()
    assert isinstance(schema, list)
    assert len(schema) > 0
    
    # Check for a standard tool
    ask_memory_tool = next((t for t in schema if t["name"] == "ask_memory"), None)
    assert ask_memory_tool is not None
    
    # Verify the key is 'inputSchema' (camelCase) for Playground compatibility
    assert "inputSchema" in ask_memory_tool
    assert "input_schema" not in ask_memory_tool

def test_get_chatgpt_tools_schema():
    """
    Tests that the specialized schema for ChatGPT Deep Research is returned,
    containing only 'search' and 'fetch' tools, and uses 'input_schema'.
    """
    schema = get_chatgpt_tools_schema()
    assert isinstance(schema, list)
    assert len(schema) == 2
    
    tool_names = {t["name"] for t in schema}
    assert tool_names == {"search", "fetch"}
    
    # Verify the keys are 'input_schema' and 'output_schema' (snake_case)
    # for OpenAI compliance.
    for tool in schema:
        assert "input_schema" in tool
        assert "output_schema" in tool
        assert "inputSchema" not in tool
        assert "outputSchema" not in tool

# --- Test ChatGPT-specific Handlers ---

@pytest.mark.asyncio
@patch("openmemory.api.app.mcp_server._search_memory_unified_impl", new_callable=AsyncMock)
async def test_handle_chatgpt_search_formatting(mock_search_impl):
    """
    Tests that handle_chatgpt_search correctly formats the raw search results
    into the OpenAI-compliant structure.
    """
    # Mock the internal search function to return a sample result
    long_memory_text = "Another memory, this one is much longer to test the title truncation feature which is a very important part of the user experience."
    mock_search_impl.return_value = json.dumps([
        {
            "id": "mem_12345",
            "content": "This is a test memory about project-alpha.",
            "metadata": {"tags": ["testing"]},
            "score": 0.95
        },
        {
            "id": "mem_67890",
            "memory": long_memory_text,
            "metadata": {},
            "score": 0.91
        }
    ])

    user_id = "test_user_123"
    query = "test query"
    
    result = await handle_chatgpt_search(user_id, query)

    # Verify the result is a dictionary with a 'results' key
    assert isinstance(result, dict)
    assert "results" in result
    
    formatted_results = result["results"]
    assert len(formatted_results) == 2

    # Check the first result's formatting
    assert formatted_results[0]["id"] == "mem_12345"
    assert formatted_results[0]["title"] == "This is a test memory about project-alpha."
    assert formatted_results[0]["text"] == "This is a test memory about project-alpha."
    assert formatted_results[0]["url"] is None

    # Check the second result's title truncation
    assert formatted_results[1]["id"] == "mem_67890"
    # Correct the expected title to match the logic `memory_text[:100] + "..."`
    expected_title = long_memory_text[:100] + "..."
    assert formatted_results[1]["title"] == expected_title
    assert formatted_results[1]["text"] == long_memory_text

    # Ensure the mock was called correctly
    mock_search_impl.assert_called_once_with(query, user_id, "chatgpt", limit=10)


@pytest.mark.asyncio
@patch("openmemory.api.app.mcp_server._get_memory_details_impl", new_callable=AsyncMock)
async def test_handle_chatgpt_fetch_formatting(mock_get_details_impl):
    """
    Tests that handle_chatgpt_fetch correctly formats the raw memory details
    into the OpenAI-compliant structure.
    """
    # Mock the internal get_details function
    mock_get_details_impl.return_value = json.dumps({
        "id": "mem_abcde",
        "content": "Full content of the fetched memory.",
        "metadata": {"source": "test", "tags": ["fetch_test"]},
        "created_at": "2024-01-01T12:00:00Z"
    })

    user_id = "test_user_456"
    memory_id = "mem_abcde"

    result = await handle_chatgpt_fetch(user_id, memory_id)

    # Verify the structure matches the spec
    assert isinstance(result, dict)
    assert result["id"] == "mem_abcde"
    assert result["title"] == "Full content of the fetched memory."
    assert result["text"] == "Full content of the fetched memory."
    assert result["url"] is None
    assert result["metadata"] == {"source": "test", "tags": ["fetch_test"]}

    # Ensure the mock was called correctly
    mock_get_details_impl.assert_called_once_with(memory_id, user_id, "chatgpt")


@pytest.mark.asyncio
@patch("openmemory.api.app.mcp_server._get_memory_details_impl", new_callable=AsyncMock)
async def test_handle_chatgpt_fetch_not_found(mock_get_details_impl):
    """
    Tests that handle_chatgpt_fetch raises a ValueError with the specific message
    'unknown id' when the underlying function fails, as per OpenAI spec.
    """
    # Configure the mock to simulate a failure (e.g., by raising an exception)
    mock_get_details_impl.side_effect = json.JSONDecodeError("Mock failure", "", 0)

    user_id = "test_user_789"
    memory_id = "non_existent_id"

    # Assert that the specific ValueError is raised
    with pytest.raises(ValueError, match="unknown id"):
        await handle_chatgpt_fetch(user_id, memory_id) 