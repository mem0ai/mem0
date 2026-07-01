from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.rerankers.openai_compatible import OpenAICompatibleRerankerConfig
from mem0.reranker.openai_compatible_reranker import OpenAICompatibleReranker


@pytest.fixture
def documents():
    return [
        {"memory": "I love hiking in the mountains"},
        {"memory": "My favorite food is pizza"},
        {"memory": "I work as a software engineer"},
    ]


def _mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestOpenAICompatibleRerankerConfig:
    def test_requires_base_url(self):
        with pytest.raises(ValueError):
            OpenAICompatibleRerankerConfig()

    def test_defaults(self):
        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1")
        assert config.base_url == "https://host/v1"
        assert config.timeout == 60.0
        assert config.headers is None
        assert config.top_k is None


class TestOpenAICompatibleRerankerInit:
    def test_builds_endpoint_and_auth_header(self):
        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1/", api_key="sk-test", model="bge-reranker")
        reranker = OpenAICompatibleReranker(config)

        assert reranker.endpoint == "https://host/v1/rerank"
        assert reranker.headers["Authorization"] == "Bearer sk-test"
        assert reranker.model == "bge-reranker"

    def test_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("RERANKER_BASE_URL", "https://env-host/v1")
        config = OpenAICompatibleRerankerConfig.model_construct(base_url=None)
        reranker = OpenAICompatibleReranker(config)
        assert reranker.endpoint == "https://env-host/v1/rerank"

    def test_missing_base_url_raises(self, monkeypatch):
        monkeypatch.delenv("RERANKER_BASE_URL", raising=False)
        config = OpenAICompatibleRerankerConfig.model_construct(base_url=None)
        with pytest.raises(ValueError):
            OpenAICompatibleReranker(config)

    def test_extra_headers_merged(self):
        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1", headers={"X-Tenant": "acme"})
        reranker = OpenAICompatibleReranker(config)
        assert reranker.headers["X-Tenant"] == "acme"


class TestOpenAICompatibleRerankerRerank:
    def test_empty_documents_returns_input(self):
        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1")
        reranker = OpenAICompatibleReranker(config)
        assert reranker.rerank("query", []) == []

    @patch("mem0.reranker.openai_compatible_reranker.httpx.post")
    def test_rerank_maps_scores_and_sorts(self, mock_post, documents):
        mock_post.return_value = _mock_response(
            {
                "results": [
                    {"index": 0, "relevance_score": 0.2},
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 1, "relevance_score": 0.5},
                ]
            }
        )

        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1", api_key="sk-test", model="bge-reranker")
        reranker = OpenAICompatibleReranker(config)
        result = reranker.rerank("what is the user's job?", documents)

        # Sorted by descending rerank_score
        assert [doc["memory"] for doc in result] == [
            "I work as a software engineer",
            "My favorite food is pizza",
            "I love hiking in the mountains",
        ]
        assert result[0]["rerank_score"] == 0.9

        # Request payload was shaped correctly
        _, kwargs = mock_post.call_args
        assert mock_post.call_args[0][0] == "https://host/v1/rerank"
        assert kwargs["json"]["query"] == "what is the user's job?"
        assert kwargs["json"]["documents"] == [
            "I love hiking in the mountains",
            "My favorite food is pizza",
            "I work as a software engineer",
        ]
        assert kwargs["json"]["model"] == "bge-reranker"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test"

    @patch("mem0.reranker.openai_compatible_reranker.httpx.post")
    def test_rerank_applies_top_k(self, mock_post, documents):
        mock_post.return_value = _mock_response(
            {
                "results": [
                    {"index": 0, "relevance_score": 0.2},
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 1, "relevance_score": 0.5},
                ]
            }
        )

        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1")
        reranker = OpenAICompatibleReranker(config)
        result = reranker.rerank("query", documents, top_k=2)

        assert len(result) == 2
        assert result[0]["memory"] == "I work as a software engineer"
        assert mock_post.call_args[1]["json"]["top_n"] == 2

    @patch("mem0.reranker.openai_compatible_reranker.httpx.post")
    def test_rerank_accepts_bare_list_response(self, mock_post, documents):
        mock_post.return_value = _mock_response(
            [
                {"index": 1, "score": 0.8},
                {"index": 0, "score": 0.1},
            ]
        )

        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1")
        reranker = OpenAICompatibleReranker(config)
        result = reranker.rerank("query", documents)

        assert result[0]["memory"] == "My favorite food is pizza"
        assert result[0]["rerank_score"] == 0.8

    @patch("mem0.reranker.openai_compatible_reranker.httpx.post")
    def test_rerank_falls_back_on_error(self, mock_post, documents):
        mock_post.side_effect = Exception("connection refused")

        config = OpenAICompatibleRerankerConfig(base_url="https://host/v1")
        reranker = OpenAICompatibleReranker(config)
        result = reranker.rerank("query", documents)

        # Original order preserved with neutral scores
        assert [doc["memory"] for doc in result] == [doc["memory"] for doc in documents]
        assert all(doc["rerank_score"] == 0.0 for doc in result)


class TestOpenAICompatibleRerankerFactory:
    def test_factory_creates_reranker(self):
        from mem0.utils.factory import RerankerFactory

        reranker = RerankerFactory.create(
            "openai_compatible",
            {"base_url": "https://host/v1", "api_key": "sk-test", "model": "bge-reranker"},
        )
        assert isinstance(reranker, OpenAICompatibleReranker)
        assert reranker.endpoint == "https://host/v1/rerank"
