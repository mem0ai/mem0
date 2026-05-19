from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.rerankers.cohere import CohereRerankerConfig
from mem0.reranker.cohere_reranker import CohereReranker


@pytest.fixture
def mock_cohere():
    with (
        patch("mem0.reranker.cohere_reranker.cohere", create=True) as mock_cohere_module,
        patch("mem0.reranker.cohere_reranker.COHERE_AVAILABLE", True),
    ):
        mock_client = MagicMock()
        mock_cohere_module.Client.return_value = mock_client
        yield mock_cohere_module, mock_client


def _make_response(results):
    """Create a fake Cohere rerank response."""
    response = MagicMock()
    response.results = []
    for index, score in results:
        result = MagicMock()
        result.index = index
        result.relevance_score = score
        response.results.append(result)
    return response


# --- Init tests ---


class TestInit:
    def test_init_sets_config_and_client(self, mock_cohere):
        mock_cohere_module, mock_client = mock_cohere
        config = CohereRerankerConfig(api_key="test-key", model="rerank-v3")
        reranker = CohereReranker(config)

        assert reranker.config is config
        assert reranker.api_key == "test-key"
        assert reranker.model == "rerank-v3"
        mock_cohere_module.Client.assert_called_once_with("test-key")

    def test_init_reads_api_key_from_env(self, mock_cohere):
        mock_cohere_module, mock_client = mock_cohere
        config = CohereRerankerConfig(api_key=None)
        with patch.dict("os.environ", {"COHERE_API_KEY": "env-key"}):
            reranker = CohereReranker(config)

        assert reranker.api_key == "env-key"

    def test_init_raises_without_api_key(self, mock_cohere):
        mock_cohere_module, mock_client = mock_cohere
        config = CohereRerankerConfig(api_key=None)
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="Cohere API key is required"):
                CohereReranker(config)

    def test_import_error_when_cohere_missing(self):
        with patch("mem0.reranker.cohere_reranker.COHERE_AVAILABLE", False):
            with pytest.raises(ImportError, match="cohere package is required"):
                CohereReranker(CohereRerankerConfig(api_key="test-key"))


# --- Rerank tests ---


class TestRerank:
    def test_empty_documents(self, mock_cohere):
        _, mock_client = mock_cohere
        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        result = reranker.rerank("query", [])

        assert result == []
        mock_client.rerank.assert_not_called()

    def test_documents_reranked_with_scores(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([
            (0, 0.3),
            (1, 0.9),
            (2, 0.5),
        ])

        config = CohereRerankerConfig(api_key="test-key", top_k=None)
        reranker = CohereReranker(config)
        docs = [{"memory": "low"}, {"memory": "high"}, {"memory": "mid"}]
        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        assert result[0]["memory"] == "low"
        assert result[0]["rerank_score"] == 0.3
        assert result[1]["memory"] == "high"
        assert result[1]["rerank_score"] == 0.9
        assert result[2]["memory"] == "mid"
        assert result[2]["rerank_score"] == 0.5

    def test_top_k_passed_to_api(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.9), (1, 0.3)])

        config = CohereRerankerConfig(api_key="test-key", top_k=None)
        reranker = CohereReranker(config)
        docs = [{"memory": "a"}, {"memory": "b"}, {"memory": "c"}]
        result = reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2
        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["top_n"] == 2

    def test_config_top_k_passed_to_api(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.9)])

        config = CohereRerankerConfig(api_key="test-key", top_k=1)
        reranker = CohereReranker(config)
        docs = [{"memory": "a"}, {"memory": "b"}]
        reranker.rerank("query", docs)

        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["top_n"] == 1

    def test_text_field_extraction(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.8)])

        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        reranker.rerank("query", [{"text": "some text"}])

        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["documents"] == ["some text"]

    def test_content_field_extraction(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.8)])

        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        reranker.rerank("query", [{"content": "some content"}])

        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["documents"] == ["some content"]

    def test_api_call_params(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.9)])

        config = CohereRerankerConfig(
            api_key="test-key",
            model="rerank-english-v3.0",
            return_documents=False,
            max_chunks_per_doc=5,
        )
        reranker = CohereReranker(config)
        docs = [{"memory": "test"}]
        reranker.rerank("query", docs)

        call_kwargs = mock_client.rerank.call_args[1]
        assert call_kwargs["model"] == "rerank-english-v3.0"
        assert call_kwargs["query"] == "query"
        assert call_kwargs["return_documents"] is False
        assert call_kwargs["max_chunks_per_doc"] == 5

    def test_fallback_on_api_error(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.side_effect = RuntimeError("API error")

        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        docs = [{"memory": "doc1"}, {"memory": "doc2"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 2
        assert result[0]["rerank_score"] == 0.0
        assert result[1]["rerank_score"] == 0.0

    def test_fallback_respects_top_k(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.side_effect = RuntimeError("API error")

        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs, top_k=1)

        assert len(result) == 1

    def test_original_doc_not_mutated(self, mock_cohere):
        _, mock_client = mock_cohere
        mock_client.rerank.return_value = _make_response([(0, 0.9)])

        reranker = CohereReranker(CohereRerankerConfig(api_key="test-key"))
        original_doc = {"memory": "test", "id": "123"}
        result = reranker.rerank("query", [original_doc])

        assert "rerank_score" not in original_doc
        assert "rerank_score" in result[0]
