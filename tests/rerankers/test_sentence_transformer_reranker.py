import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker


@pytest.fixture
def mock_cross_encoder():
    with patch("mem0.reranker.sentence_transformer_reranker.CrossEncoder") as mock_cls:
        mock_model = MagicMock()
        mock_cls.return_value = mock_model
        yield mock_cls, mock_model


@pytest.fixture
def mock_sentence_transformer():
    with patch("mem0.reranker.sentence_transformer_reranker.SentenceTransformer") as mock_cls:
        mock_model = MagicMock()
        mock_cls.return_value = mock_model
        yield mock_cls, mock_model


class TestDetectCrossEncoder:
    def test_cross_encoder_prefix(self):
        assert SentenceTransformerReranker._detect_cross_encoder("cross-encoder/ms-marco-MiniLM-L-6-v2") is True

    def test_reranker_in_name(self):
        assert SentenceTransformerReranker._detect_cross_encoder("BAAI/bge-reranker-base") is True

    def test_regular_model(self):
        assert SentenceTransformerReranker._detect_cross_encoder("all-MiniLM-L6-v2") is False

    def test_empty_string(self):
        assert SentenceTransformerReranker._detect_cross_encoder("") is False

    def test_none(self):
        assert SentenceTransformerReranker._detect_cross_encoder(None) is False

    def test_case_insensitive(self):
        assert SentenceTransformerReranker._detect_cross_encoder("Cross-Encoder/ms-marco-MiniLM-L-6-v2") is True


class TestInit:
    def test_cross_encoder_model_uses_cross_encoder_class(self, mock_cross_encoder):
        mock_cls, _ = mock_cross_encoder
        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        mock_cls.assert_called_once_with("cross-encoder/ms-marco-MiniLM-L-6-v2", device=None)
        assert reranker._is_cross_encoder is True

    def test_bi_encoder_model_uses_sentence_transformer_class(self, mock_sentence_transformer):
        mock_cls, _ = mock_sentence_transformer
        reranker = SentenceTransformerReranker({
            "model": "all-MiniLM-L6-v2",
        })
        mock_cls.assert_called_once_with("all-MiniLM-L6-v2", device=None)
        assert reranker._is_cross_encoder is False

    def test_default_model_is_cross_encoder(self, mock_cross_encoder):
        mock_cls, _ = mock_cross_encoder
        reranker = SentenceTransformerReranker({})
        mock_cls.assert_called_once()
        assert reranker._is_cross_encoder is True


class TestRerank:
    def test_empty_documents(self, mock_cross_encoder):
        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        result = reranker.rerank("query", [])
        assert result == []

    def test_documents_sorted_by_score_descending(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])

        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        docs = [
            {"memory": "low relevance"},
            {"memory": "high relevance"},
            {"memory": "mid relevance"},
        ]

        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        assert result[0]["memory"] == "high relevance"
        assert result[0]["rerank_score"] == pytest.approx(0.9)
        assert result[1]["memory"] == "mid relevance"
        assert result[2]["memory"] == "low relevance"

    def test_top_k_limits_results(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([0.3, 0.9, 0.6])

        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        docs = [
            {"memory": "low"},
            {"memory": "high"},
            {"memory": "mid"},
        ]

        result = reranker.rerank("test query", docs, top_k=2)
        assert len(result) == 2
        assert result[0]["memory"] == "high"

    def test_extracts_text_from_different_keys(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.return_value = np.array([0.8, 0.5, 0.3])

        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        docs = [
            {"memory": "from memory key"},
            {"text": "from text key"},
            {"content": "from content key"},
        ]

        reranker.rerank("query", docs)

        pairs = mock_model.predict.call_args[0][0]
        assert pairs[0] == ["query", "from memory key"]
        assert pairs[1] == ["query", "from text key"]
        assert pairs[2] == ["query", "from content key"]

    def test_fallback_on_predict_failure(self, mock_cross_encoder):
        _, mock_model = mock_cross_encoder
        mock_model.predict.side_effect = RuntimeError("model error")

        reranker = SentenceTransformerReranker({
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        })
        docs = [
            {"memory": "doc1"},
            {"memory": "doc2"},
        ]

        result = reranker.rerank("query", docs)
        assert len(result) == 2
        assert all(doc["rerank_score"] == 0.0 for doc in result)
