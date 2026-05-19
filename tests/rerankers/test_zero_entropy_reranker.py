from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig
from mem0.reranker.zero_entropy_reranker import ZeroEntropyReranker


@pytest.fixture
def mock_zero_entropy():
    with (
        patch("mem0.reranker.zero_entropy_reranker.ZeroEntropy", create=True) as mock_ze_cls,
        patch("mem0.reranker.zero_entropy_reranker.ZERO_ENTROPY_AVAILABLE", True),
    ):
        mock_client = MagicMock()
        mock_ze_cls.return_value = mock_client
        yield mock_ze_cls, mock_client


def _make_response(results):
    """Create a fake ZeroEntropy rerank response."""
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
    def test_init_sets_config_and_client(self, mock_zero_entropy):
        mock_ze_cls, mock_client = mock_zero_entropy
        config = ZeroEntropyRerankerConfig(api_key="test-key", model="zerank-1")
        reranker = ZeroEntropyReranker(config)

        assert reranker.config is config
        assert reranker.api_key == "test-key"
        assert reranker.model == "zerank-1"
        mock_ze_cls.assert_called_once_with(api_key="test-key")

    def test_init_reads_api_key_from_env(self, mock_zero_entropy):
        mock_ze_cls, _ = mock_zero_entropy
        config = ZeroEntropyRerankerConfig(api_key=None)
        with patch.dict("os.environ", {"ZERO_ENTROPY_API_KEY": "env-key"}):
            reranker = ZeroEntropyReranker(config)

        assert reranker.api_key == "env-key"

    def test_init_raises_without_api_key(self, mock_zero_entropy):
        mock_ze_cls, _ = mock_zero_entropy
        config = ZeroEntropyRerankerConfig(api_key=None)
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="Zero Entropy API key is required"):
                ZeroEntropyReranker(config)

    def test_init_defaults_model(self, mock_zero_entropy):
        mock_ze_cls, _ = mock_zero_entropy
        config = ZeroEntropyRerankerConfig(api_key="test-key")
        reranker = ZeroEntropyReranker(config)

        assert reranker.model == "zerank-1"

    def test_import_error_when_zero_entropy_missing(self):
        with patch("mem0.reranker.zero_entropy_reranker.ZERO_ENTROPY_AVAILABLE", False):
            with pytest.raises(ImportError, match="zeroentropy package is required"):
                ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))


# --- Rerank tests ---


class TestRerank:
    def test_empty_documents(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        result = reranker.rerank("query", [])

        assert result == []
        mock_client.models.rerank.assert_not_called()

    def test_documents_reranked_with_scores(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([
            (0, 0.3),
            (1, 0.9),
            (2, 0.5),
        ])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        docs = [{"memory": "low"}, {"memory": "high"}, {"memory": "mid"}]
        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        # ZeroEntropy sorts by score descending after mapping
        assert result[0]["memory"] == "high"
        assert result[0]["rerank_score"] == 0.9
        assert result[1]["memory"] == "mid"
        assert result[1]["rerank_score"] == 0.5
        assert result[2]["memory"] == "low"
        assert result[2]["rerank_score"] == 0.3

    def test_top_k_limits_results(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([
            (0, 0.9),
            (1, 0.8),
            (2, 0.3),
        ])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2

    def test_config_top_k_limits_results(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([
            (0, 0.9),
            (1, 0.8),
            (2, 0.3),
        ])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key", top_k=1))
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs)

        assert len(result) == 1

    def test_text_field_extraction(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([(0, 0.8)])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        reranker.rerank("query", [{"text": "some text"}])

        call_kwargs = mock_client.models.rerank.call_args[1]
        assert call_kwargs["documents"] == ["some text"]

    def test_content_field_extraction(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([(0, 0.8)])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        reranker.rerank("query", [{"content": "some content"}])

        call_kwargs = mock_client.models.rerank.call_args[1]
        assert call_kwargs["documents"] == ["some content"]

    def test_api_call_params(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([(0, 0.9)])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key", model="zerank-1"))
        docs = [{"memory": "test"}]
        reranker.rerank("query", docs)

        call_kwargs = mock_client.models.rerank.call_args[1]
        assert call_kwargs["model"] == "zerank-1"
        assert call_kwargs["query"] == "query"
        assert call_kwargs["documents"] == ["test"]

    def test_fallback_on_api_error(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        docs = [{"memory": "doc1"}, {"memory": "doc2"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 2
        assert result[0]["rerank_score"] == 0.0
        assert result[1]["rerank_score"] == 0.0

    def test_fallback_respects_top_k(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs, top_k=1)

        assert len(result) == 1

    def test_original_doc_not_mutated(self, mock_zero_entropy):
        _, mock_client = mock_zero_entropy
        mock_client.models.rerank.return_value = _make_response([(0, 0.9)])

        reranker = ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        original_doc = {"memory": "test", "id": "123"}
        result = reranker.rerank("query", [original_doc])

        assert "rerank_score" not in original_doc
        assert "rerank_score" in result[0]
