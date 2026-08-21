from unittest.mock import Mock, patch

import pytest

from mem0.configs.rerankers.aws_bedrock import AWSBedrockRerankerConfig
from mem0.reranker.aws_bedrock_reranker import AWSBedrockReranker


@pytest.fixture
def mock_boto3_client():
    with patch("mem0.reranker.aws_bedrock_reranker.boto3.client") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client


def _docs(n):
    return [{"memory": f"doc{i}"} for i in range(n)]


def _rerank_response(*index_score_pairs):
    return {"results": [{"index": i, "relevanceScore": s} for i, s in index_score_pairs]}


class TestAWSBedrockRerankerInit:
    def test_default_model_and_region(self, mock_boto3_client):
        with patch("mem0.reranker.aws_bedrock_reranker.os.environ", {}):
            reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())

        _, kwargs = mock_boto3_client.call_args
        assert mock_boto3_client.call_args[0][0] == "bedrock-agent-runtime"
        assert kwargs["region_name"] == "us-west-2"
        assert reranker.model_arn == "arn:aws:bedrock:us-west-2::foundation-model/cohere.rerank-v3-5:0"

    def test_short_model_id_is_expanded_to_region_scoped_arn(self, mock_boto3_client):
        config = AWSBedrockRerankerConfig(model="amazon.rerank-v1:0", aws_region="eu-central-1")
        reranker = AWSBedrockReranker(config)

        assert reranker.model_arn == "arn:aws:bedrock:eu-central-1::foundation-model/amazon.rerank-v1:0"

    def test_full_arn_is_passed_through_unchanged(self, mock_boto3_client):
        arn = "arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0"
        config = AWSBedrockRerankerConfig(model=arn, aws_region="us-west-2")
        reranker = AWSBedrockReranker(config)

        assert reranker.model_arn == arn

    def test_credentials_from_config_reach_client(self, mock_boto3_client):
        config = AWSBedrockRerankerConfig(
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="SECRET_TEST",
            aws_session_token="SESSION_TOKEN_TEST",
            aws_region="ap-southeast-1",
        )
        AWSBedrockReranker(config)

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["aws_access_key_id"] == "AKIA_TEST"
        assert kwargs["aws_secret_access_key"] == "SECRET_TEST"
        assert kwargs["aws_session_token"] == "SESSION_TOKEN_TEST"
        assert kwargs["region_name"] == "ap-southeast-1"

    def test_credentials_fall_back_to_env(self, mock_boto3_client):
        env = {
            "AWS_REGION": "eu-west-1",
            "AWS_ACCESS_KEY_ID": "ENV_KEY",
            "AWS_SECRET_ACCESS_KEY": "ENV_SECRET",
            "AWS_SESSION_TOKEN": "ENV_TOKEN",
        }
        with patch("mem0.reranker.aws_bedrock_reranker.os.environ", env):
            AWSBedrockReranker(AWSBedrockRerankerConfig())

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["aws_access_key_id"] == "ENV_KEY"
        assert kwargs["aws_secret_access_key"] == "ENV_SECRET"
        assert kwargs["aws_session_token"] == "ENV_TOKEN"


class TestAWSBedrockRerankerRerank:
    def test_rerank_maps_index_and_relevance_score(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())
        reranker.client.rerank.return_value = _rerank_response((1, 0.9), (0, 0.4))

        docs = _docs(2)
        result = reranker.rerank("query", docs)

        assert [d["memory"] for d in result] == ["doc1", "doc0"]
        assert result[0]["rerank_score"] == 0.9
        assert result[1]["rerank_score"] == 0.4

    def test_rerank_sends_expected_request_shape(self, mock_boto3_client):
        config = AWSBedrockRerankerConfig(model="amazon.rerank-v1:0", aws_region="us-east-1", top_k=3)
        reranker = AWSBedrockReranker(config)
        reranker.client.rerank.return_value = _rerank_response((0, 0.5))

        reranker.rerank("what does the user do", [{"memory": "alpha"}])

        _, call_kwargs = reranker.client.rerank.call_args
        assert call_kwargs["queries"] == [{"textQuery": {"text": "what does the user do"}, "type": "TEXT"}]
        assert call_kwargs["sources"] == [
            {
                "inlineDocumentSource": {"textDocument": {"text": "alpha"}, "type": "TEXT"},
                "type": "INLINE",
            }
        ]
        reranking_config = call_kwargs["rerankingConfiguration"]
        assert reranking_config["type"] == "BEDROCK_RERANKING_MODEL"
        bedrock_config = reranking_config["bedrockRerankingConfiguration"]
        assert bedrock_config["modelConfiguration"]["modelArn"] == (
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.rerank-v1:0"
        )
        assert bedrock_config["numberOfResults"] == 3

    def test_number_of_results_defaults_to_document_count(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())
        reranker.client.rerank.return_value = _rerank_response((0, 0.1), (1, 0.2), (2, 0.3))

        reranker.rerank("query", _docs(3))

        _, call_kwargs = reranker.client.rerank.call_args
        number_of_results = call_kwargs["rerankingConfiguration"]["bedrockRerankingConfiguration"]["numberOfResults"]
        assert number_of_results == 3

    def test_empty_documents_returns_empty_without_calling_client(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())

        result = reranker.rerank("query", [])

        assert result == []
        reranker.client.rerank.assert_not_called()

    def test_text_extraction_prefers_memory_then_text_then_content(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())
        reranker.client.rerank.return_value = _rerank_response((0, 1.0), (1, 1.0), (2, 1.0))

        docs = [{"memory": "m", "text": "t"}, {"text": "t2", "content": "c2"}, {"content": "c3"}]
        reranker.rerank("query", docs)

        _, call_kwargs = reranker.client.rerank.call_args
        texts = [s["inlineDocumentSource"]["textDocument"]["text"] for s in call_kwargs["sources"]]
        assert texts == ["m", "t2", "c3"]


class TestAWSBedrockRerankerFallback:
    def test_fallback_respects_config_top_k(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig(top_k=2))
        reranker.client.rerank.side_effect = RuntimeError("throttled")

        result = reranker.rerank("query", _docs(5))

        assert len(result) == 2
        assert all(d["rerank_score"] == 0.0 for d in result)

    def test_fallback_per_call_top_k_overrides_config(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig(top_k=4))
        reranker.client.rerank.side_effect = RuntimeError("throttled")

        result = reranker.rerank("query", _docs(5), top_k=1)

        assert len(result) == 1

    def test_fallback_returns_all_when_no_top_k(self, mock_boto3_client):
        reranker = AWSBedrockReranker(AWSBedrockRerankerConfig())
        reranker.client.rerank.side_effect = RuntimeError("throttled")

        result = reranker.rerank("query", _docs(5))

        assert len(result) == 5
