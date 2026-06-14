from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.sentence_transformer import (
    SentenceTransformerRerankerConfig,
)
from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker


@pytest.fixture
def mock_cross_encoder():
    with patch("mem0.reranker.sentence_transformer_reranker.CrossEncoder") as mock_ce_cls:
        mock_model = MagicMock()
        mock_ce_cls.return_value = mock_model
        yield mock_ce_cls, mock_model


# --- Init tests ---


class TestInit:
    def test_init_from_dict(self, mock_cross_encoder):
        mock_ce_cls, _ = mock_cross_encoder
        config = {"model": "cross-encoder/test", "batch_size": 16}
        reranker = SentenceTransformerReranker(config)

        assert isinstance(reranker.config, SentenceTransformerRerankerConfig)
        assert reranker.config.model == "cross-encoder/test"
        assert reranker.config.batch_size == 16

    def test_init_from_sentence_transformer_config(self, mock_cross_encoder):
        mock_ce_cls, _ = mock_cross_encoder
        config = SentenceTransformerRerankerConfig(model="my-model", device="cuda")
        SentenceTransformerReranker(config)

        mock_ce_cls.assert_called_once_with("my-model", device="cuda")

    def test_init_from_base_config_converts(self, mock_cross_encoder):
        base_config = BaseRerankerConfig(provider="sentence_transformer", top_k=5)
        reranker = SentenceTransformerReranker(base_config)

        assert isinstance(reranker.config, SentenceTransformerRerankerConfig)
        assert reranker.config.top_k == 5

    def test_init_import_error_when_missing(self):
        with patch("mem0.reranker.sentence_transformer_reranker.SENTENCE_TRANSFORMERS_AVAILABLE", False):
            with pytest.raises(ImportError, match="sentence-transformers package is required"):
                SentenceTransformerReranker({"model": "test"})


# --- Rerank tests ---


class TestRerank:
    def test_empty_documents(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        reranker = SentenceTransformerReranker({"model": "test"})
        result = reranker.rerank("query", [])

        assert result == []
        mock_model.predict.assert_not_called()

    def test_single_document(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([5.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        docs = [{"memory": "hello world"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 1
        assert "rerank_score" in result[0]
        assert result[0]["memory"] == "hello world"

    def test_documents_sorted_by_score_descending(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([2.0, 9.0, 4.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        docs = [{"memory": "low"}, {"memory": "high"}, {"memory": "mid"}]
        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        assert result[0]["memory"] == "high"
        assert result[1]["memory"] == "mid"
        assert result[2]["memory"] == "low"

    def test_top_k_limits_results(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([1.0, 3.0, 2.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2

    def test_config_top_k_used_when_arg_not_provided(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([1.0, 3.0, 2.0])

        reranker = SentenceTransformerReranker({"model": "test", "top_k": 1})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs)

        assert len(result) == 1

    def test_text_field_extraction(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([5.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        reranker.rerank("query", [{"text": "some text"}])

        call_args = mock_model.predict.call_args
        pairs = call_args[0][0]
        assert any("some text" in pair for pair in pairs)

    def test_content_field_extraction(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([5.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        reranker.rerank("query", [{"content": "some content"}])

        call_args = mock_model.predict.call_args
        pairs = call_args[0][0]
        assert any("some content" in pair for pair in pairs)

    def test_predict_called_with_correct_params(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([1.0])

        reranker = SentenceTransformerReranker({"model": "test", "batch_size": 16, "show_progress_bar": False})
        reranker.rerank("query", [{"memory": "doc"}])

        call_kwargs = mock_model.predict.call_args[1]
        assert call_kwargs["batch_size"] == 16
        assert call_kwargs["show_progress_bar"] is False

    def test_predict_returns_list_converted(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = [1.0, 3.0, 2.0]

        reranker = SentenceTransformerReranker({"model": "test"})
        docs = [{"memory": "a"}, {"memory": "b"}, {"memory": "c"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 3
        assert result[0]["memory"] == "b"

    def test_fallback_on_model_error(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.side_effect = RuntimeError("model error")

        reranker = SentenceTransformerReranker({"model": "test"})
        docs = [{"memory": "doc1"}, {"memory": "doc2"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 2
        assert result[0]["rerank_score"] == 0.0
        assert result[1]["rerank_score"] == 0.0

    def test_fallback_respects_top_k(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.side_effect = RuntimeError("model error")

        reranker = SentenceTransformerReranker({"model": "test", "top_k": 1})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs)

        assert len(result) == 1

    def test_original_doc_not_mutated(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([5.0])

        reranker = SentenceTransformerReranker({"model": "test"})
        original_doc = {"memory": "test", "id": "123"}
        result = reranker.rerank("query", [original_doc])

        assert "rerank_score" not in original_doc
        assert "rerank_score" in result[0]
