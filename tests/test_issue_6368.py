"""Regression test for Anthropic Converse reasoning-content responses."""

from unittest.mock import MagicMock, patch

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM


def test_issue_6368():
    """Anthropic Converse responses must skip reasoningContent blocks."""
    with patch.object(AWSBedrockLLM, "_initialize_aws_client"):
        llm = AWSBedrockLLM(AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0"))

    llm.client = MagicMock()
    llm.client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {"reasoningContent": {"reasoningText": {"text": "Let me think..."}}},
                    {"text": "Hello!"},
                ]
            }
        }
    }

    result = llm.generate_response([{"role": "user", "content": "Say hi"}])

    assert result == "Hello!"
