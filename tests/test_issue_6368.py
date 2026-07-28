from unittest.mock import MagicMock, patch

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM


def test_issue_6368():
    runtime_client = MagicMock()
    bedrock_client = MagicMock()
    bedrock_client.list_foundation_models.return_value = {"modelSummaries": []}

    def mock_client(service, **kwargs):
        if service == "bedrock-runtime":
            return runtime_client
        return bedrock_client

    runtime_client.converse.return_value = {
        "output": {
            "message": {
                "content": [
                    {"reasoningContent": {"reasoningText": {"text": "Thinking through the request."}}},
                    {"text": "The generated response."},
                ]
            }
        }
    }

    with patch("mem0.llms.aws_bedrock.boto3") as mock_boto3:
        mock_boto3.client.side_effect = mock_client
        llm = AWSBedrockLLM(AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0"))

    response = llm.generate_response([{"role": "user", "content": "Respond to this request."}])

    assert response == "The generated response."
    runtime_client.converse.assert_called_once()
