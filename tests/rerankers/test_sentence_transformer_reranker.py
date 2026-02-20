from unittest.mock import Mock, patch, MagicMock

import numpy as np
import pytest

from mem0.configs.rerankers.sentence_transformer import SentenceTransformerRerankerConfig
from mem0.reranker.sentence_transformer_reranker import (
    _is_cross_encoder_model,
)

# sentence_transformers may not be installed in the test environment.
# We patch both SentenceTransformer and CrossEncoder with create=True so that
# the patch works regardless of whether the real library is present.
_ST_MOD = "mem0.reranker.sentence_transformer_reranker"


def _make_reranker_cls():
    """Import SentenceTransformerReranker inside the patched context."""
    # Re-import to pick up the patched names.  We also need to ensure the
    # availability flag is True so the constructor does not raise.
    import mem0.reranker.sentence_transformer_reranker as mod
    mod.SENTENCE_TRANSFORMERS_AVAILABLE = True
    return mod.SentenceTransformerReranker


# ---------------------------------------------------------------------------
# Unit tests for _is_cross_encoder_model helper
# ---------------------------------------------------------------------------

class TestIsCrossEncoderModel:
    def test_cross_encoder_prefix(self):
        assert _is_cross_encoder_model("cross-encoder/ms-marco-MiniLM-L-6-v2") is True

    def test_cross_encoder_prefix_uppercase(self):
        assert _is_cross_encoder_model("Cross-Encoder/ms-marco-MiniLM-L-6-v2") is True

    def test_reranker_keyword(self):
        assert _is_cross_encoder_model("BAAI/bge-reranker-base") is True

    def test_reranker_keyword_uppercase(self):
        assert _is_cross_encoder_model("BAAI/bge-Reranker-large") is True

    def test_regular_sentence_transformer(self):
        assert _is_cross_encoder_model("all-MiniLM-L6-v2") is False

    def test_custom_embedding_model(self):
        assert _is_cross_encoder_model("sentence-transformers/all-mpnet-base-v2") is False


# ---------------------------------------------------------------------------
# Unit tests for SentenceTransformerReranker initialisation
# ---------------------------------------------------------------------------

class TestSentenceTransformerRerankerInit:
    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    @patch(f"{_ST_MOD}.SentenceTransformer", create=True)
    def test_default_model_uses_cross_encoder(self, mock_st, mock_ce):
        """The default model is a cross-encoder and must be loaded with CrossEncoder."""
        cls = _make_reranker_cls()
        config = SentenceTransformerRerankerConfig()  # default model
        reranker = cls(config)

        mock_ce.assert_called_once_with(config.model, device=config.device)
        mock_st.assert_not_called()
        assert reranker._is_cross_encoder is True

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    @patch(f"{_ST_MOD}.SentenceTransformer", create=True)
    def test_explicit_cross_encoder_model(self, mock_st, mock_ce):
        cls = _make_reranker_cls()
        config = SentenceTransformerRerankerConfig(model="cross-encoder/ms-marco-TinyBERT-L-2-v2")
        reranker = cls(config)

        mock_ce.assert_called_once()
        mock_st.assert_not_called()
        assert reranker._is_cross_encoder is True

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    @patch(f"{_ST_MOD}.SentenceTransformer", create=True)
    def test_reranker_model_uses_cross_encoder(self, mock_st, mock_ce):
        cls = _make_reranker_cls()
        config = SentenceTransformerRerankerConfig(model="BAAI/bge-reranker-base")
        reranker = cls(config)

        mock_ce.assert_called_once()
        mock_st.assert_not_called()
        assert reranker._is_cross_encoder is True

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    @patch(f"{_ST_MOD}.SentenceTransformer", create=True)
    def test_bi_encoder_model_uses_sentence_transformer(self, mock_st, mock_ce):
        cls = _make_reranker_cls()
        config = SentenceTransformerRerankerConfig(model="all-MiniLM-L6-v2")
        reranker = cls(config)

        mock_st.assert_called_once_with("all-MiniLM-L6-v2", device=config.device)
        mock_ce.assert_not_called()
        assert reranker._is_cross_encoder is False

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    @patch(f"{_ST_MOD}.SentenceTransformer", create=True)
    def test_dict_config_cross_encoder(self, mock_st, mock_ce):
        """Passing a plain dict should still detect cross-encoder models."""
        cls = _make_reranker_cls()
        reranker = cls({"model": "cross-encoder/ms-marco-MiniLM-L-6-v2"})

        mock_ce.assert_called_once()
        mock_st.assert_not_called()
        assert reranker._is_cross_encoder is True


# ---------------------------------------------------------------------------
# Unit tests for rerank method
# ---------------------------------------------------------------------------

class TestSentenceTransformerRerankerRerank:
    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_returns_sorted_results(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.1, 0.9, 0.5])
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [
            {"memory": "doc A"},
            {"memory": "doc B"},
            {"memory": "doc C"},
        ]
        results = reranker.rerank("query", docs)

        assert len(results) == 3
        # Highest score first
        assert results[0]["memory"] == "doc B"
        assert results[0]["rerank_score"] == pytest.approx(0.9)
        assert results[1]["memory"] == "doc C"
        assert results[1]["rerank_score"] == pytest.approx(0.5)
        assert results[2]["memory"] == "doc A"
        assert results[2]["rerank_score"] == pytest.approx(0.1)

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_with_top_k(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.1, 0.9, 0.5])
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [
            {"memory": "doc A"},
            {"memory": "doc B"},
            {"memory": "doc C"},
        ]
        results = reranker.rerank("query", docs, top_k=2)

        assert len(results) == 2
        assert results[0]["memory"] == "doc B"
        assert results[1]["memory"] == "doc C"

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_empty_documents(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_ce_cls.return_value = MagicMock()
        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        results = reranker.rerank("query", [])
        assert results == []

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_fallback_on_error(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("model error")
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [{"memory": "doc A"}, {"memory": "doc B"}]
        results = reranker.rerank("query", docs)

        # Fallback: original order, score 0.0
        assert len(results) == 2
        assert results[0]["rerank_score"] == 0.0
        assert results[1]["rerank_score"] == 0.0

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_extracts_text_field(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.8])
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [{"text": "some text"}]
        results = reranker.rerank("query", docs)

        # The pairs passed to predict should use the 'text' field
        call_args = mock_model.predict.call_args[0][0]
        assert call_args == [["query", "some text"]]

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_extracts_content_field(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.7])
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [{"content": "some content"}]
        results = reranker.rerank("query", docs)

        call_args = mock_model.predict.call_args[0][0]
        assert call_args == [["query", "some content"]]

    @patch(f"{_ST_MOD}.CrossEncoder", create=True)
    def test_rerank_does_not_mutate_original_docs(self, mock_ce_cls):
        cls = _make_reranker_cls()
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.5, 0.9])
        mock_ce_cls.return_value = mock_model

        config = SentenceTransformerRerankerConfig()
        reranker = cls(config)

        docs = [{"memory": "A"}, {"memory": "B"}]
        results = reranker.rerank("query", docs)

        # Original docs should not have rerank_score
        assert "rerank_score" not in docs[0]
        assert "rerank_score" not in docs[1]
        # Results should have rerank_score
        assert "rerank_score" in results[0]
        assert "rerank_score" in results[1]
