from unittest.mock import MagicMock, patch

import pytest
import torch

from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.huggingface import HuggingFaceRerankerConfig
from mem0.reranker.huggingface_reranker import HuggingFaceReranker


@pytest.fixture
def mock_hf_components():
    """Mock AutoTokenizer, AutoModelForSequenceClassification, and torch.cuda."""
    with (
        patch("mem0.reranker.huggingface_reranker.AutoTokenizer") as mock_tokenizer_cls,
        patch("mem0.reranker.huggingface_reranker.AutoModelForSequenceClassification") as mock_model_cls,
        patch("mem0.reranker.huggingface_reranker.torch") as mock_torch,
    ):
        mock_tokenizer = MagicMock()
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model

        # Default: CPU
        mock_torch.cuda.is_available.return_value = False

        yield mock_tokenizer, mock_model, mock_torch


def _make_outputs(logits_values):
    """Create a fake model output with given logit values."""
    mock_outputs = MagicMock()
    logits = torch.tensor(logits_values).unsqueeze(-1).float()
    mock_outputs.logits = logits
    return mock_outputs


# --- Init tests ---


class TestInit:
    def test_init_from_dict(self, mock_hf_components):
        mock_tokenizer, mock_model, mock_torch = mock_hf_components
        config = {"model": "test-model", "batch_size": 16}
        reranker = HuggingFaceReranker(config)

        assert isinstance(reranker.config, HuggingFaceRerankerConfig)
        assert reranker.config.model == "test-model"
        assert reranker.config.batch_size == 16
        assert reranker.device == "cpu"

    def test_init_from_huggingface_config(self, mock_hf_components):
        config = HuggingFaceRerankerConfig(model="my-model", device="cuda")
        reranker = HuggingFaceReranker(config)

        assert reranker.device == "cuda"

    def test_init_from_base_config_converts(self, mock_hf_components):
        base_config = BaseRerankerConfig(provider="huggingface", top_k=5)
        reranker = HuggingFaceReranker(base_config)

        assert isinstance(reranker.config, HuggingFaceRerankerConfig)
        assert reranker.config.top_k == 5

    def test_init_auto_detects_cuda(self, mock_hf_components):
        _, _, mock_torch = mock_hf_components
        mock_torch.cuda.is_available.return_value = True

        reranker = HuggingFaceReranker({"model": "test"})

        assert reranker.device == "cuda"

    def test_import_error_when_transformers_missing(self):
        with patch("mem0.reranker.huggingface_reranker.TRANSFORMERS_AVAILABLE", False):
            with pytest.raises(ImportError, match="transformers package is required"):
                HuggingFaceReranker({"model": "test"})


# --- Rerank tests ---


class TestRerank:
    def test_empty_documents(self, mock_hf_components):
        reranker = HuggingFaceReranker({"model": "test"})
        result = reranker.rerank("query", [])
        assert result == []

    def test_single_document(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([5.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        docs = [{"memory": "hello world"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 1
        assert "rerank_score" in result[0]
        assert result[0]["memory"] == "hello world"

    def test_documents_sorted_by_score_descending(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        # Simulate: doc0 gets score 2.0, doc1 gets score 9.0, doc2 gets score 4.0
        mock_model.side_effect = lambda *a, **kw: _make_outputs([2.0, 9.0, 4.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        docs = [
            {"memory": "low"},
            {"memory": "high"},
            {"memory": "mid"},
        ]
        result = reranker.rerank("test query", docs)

        assert len(result) == 3
        assert result[0]["memory"] == "high"
        assert result[1]["memory"] == "mid"
        assert result[2]["memory"] == "low"

    def test_top_k_limits_results(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([1.0, 3.0, 2.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2

    def test_config_top_k_used_when_arg_not_provided(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([1.0, 3.0, 2.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False, "top_k": 1})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs)

        assert len(result) == 1

    def test_text_field_extraction(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([5.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        reranker.rerank("query", [{"text": "some text"}])

        call_args = mock_tokenizer.call_args[0][0]
        assert any("some text" in pair for pair in call_args)

    def test_content_field_extraction(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([5.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        reranker.rerank("query", [{"content": "some content"}])

        call_args = mock_tokenizer.call_args[0][0]
        assert any("some content" in pair for pair in call_args)

    def test_fallback_score_on_model_error(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = RuntimeError("model error")

        reranker = HuggingFaceReranker({"model": "test"})
        docs = [{"memory": "doc1"}, {"memory": "doc2"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 2
        assert result[0]["rerank_score"] == 0.0
        assert result[1]["rerank_score"] == 0.0

    def test_fallback_respects_top_k(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = RuntimeError("model error")

        reranker = HuggingFaceReranker({"model": "test", "top_k": 1})
        docs = [{"memory": f"doc{i}"} for i in range(3)]
        result = reranker.rerank("query", docs)

        assert len(result) == 1

    def test_normalize_scores(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        # Raw scores: 2.0, 8.0, 5.0 → normalized: 0.0, 1.0, 0.5
        mock_model.side_effect = lambda *a, **kw: _make_outputs([2.0, 8.0, 5.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": True})
        docs = [{"memory": "low"}, {"memory": "high"}, {"memory": "mid"}]
        result = reranker.rerank("query", docs)

        assert result[0]["rerank_score"] == pytest.approx(1.0)
        assert result[1]["rerank_score"] == pytest.approx(0.5)
        assert result[2]["rerank_score"] == pytest.approx(0.0)

    def test_no_normalize_when_disabled(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([2.0, 8.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        docs = [{"memory": "a"}, {"memory": "b"}]
        result = reranker.rerank("query", docs)

        assert result[0]["rerank_score"] == 8.0
        assert result[1]["rerank_score"] == 2.0

    def test_batch_processing(self, mock_hf_components):
        """When docs exceed batch_size, tokenizer should be called multiple times."""
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([1.0, 2.0, 3.0, 4.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False, "batch_size": 2})
        docs = [{"memory": f"doc{i}"} for i in range(4)]
        reranker.rerank("query", docs)

        # batch_size=2, 4 docs → 2 batches
        assert mock_tokenizer.call_count == 2

    def test_original_doc_not_mutated(self, mock_hf_components):
        mock_tokenizer, mock_model, _ = mock_hf_components
        mock_model.side_effect = lambda *a, **kw: _make_outputs([5.0])
        mock_tokenizer.return_value.to.return_value = MagicMock()

        reranker = HuggingFaceReranker({"model": "test", "normalize": False})
        original_doc = {"memory": "test", "id": "123"}
        result = reranker.rerank("query", [original_doc])

        assert "rerank_score" not in original_doc
        assert "rerank_score" in result[0]
