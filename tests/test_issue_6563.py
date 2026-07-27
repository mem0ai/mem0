"""Regression tests for Bedrock Converse tool-call message formatting."""

from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM


@pytest.mark.parametrize(
    "model",
    [
        "amazon.nova-3-mini-20241119-v1:0",
        "cohere.command-r-v1:0",
    ],
)
def test_issue_6563(model):
    """Tool-enabled Converse requests must preserve system and conversation messages."""
    runtime_client = MagicMock()
    bedrock_client = MagicMock()
    bedrock_client.list_foundation_models.return_value = {"modelSummaries": []}
    runtime_client.converse.return_value = {"output": {"message": {"content": []}}}

    def _client(service, **kwargs):
        if service == "bedrock-runtime":
            return runtime_client
        return bedrock_client

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Remember that I prefer tea."},
        {"role": "assistant", "content": "I will remember that."},
        {"role": "user", "content": "What do I prefer?"},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_preference",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    with patch("mem0.llms.aws_bedrock.boto3.client", side_effect=_client):
        llm = AWSBedrockLLM(AWSBedrockConfig(model=model))
        llm.generate_response(messages, tools=tools)

    _, kwargs = runtime_client.converse.call_args
    assert kwargs["system"] == [{"text": "You are a helpful assistant."}]
    assert kwargs["messages"] == [
        {"role": "user", "content": [{"text": "Remember that I prefer tea."}]},
        {"role": "assistant", "content": [{"text": "I will remember that."}]},
        {"role": "user", "content": [{"text": "What do I prefer?"}]},
    ]
