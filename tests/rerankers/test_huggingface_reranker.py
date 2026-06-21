"""Tests for HuggingFaceReranker score normalization."""

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from mem0.configs.rerankers.huggingface import HuggingFaceRerankerConfig


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class _FakeTensor:
    def __init__(self, values):
        self._values = np.asarray(values, dtype=np.float32)

    @property
    def ndim(self):
        return self._values.ndim

    def squeeze(self, dim=-1):
        return _FakeTensor(self._values.squeeze())

    def cpu(self):
        return self

    def numpy(self):
        return self._values

    def tolist(self):
        return self._values.tolist()


@pytest.fixture
def mock_huggingface_reranker(monkeypatch):
    """Provide a fake ``transformers`` module so HuggingFaceReranker can be constructed."""
    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(is_available=lambda: False)

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *args):
            return False

    fake_torch.no_grad = _NoGrad

    fake_transformers = ModuleType("transformers")
    fake_transformers.AutoTokenizer = MagicMock()
    fake_transformers.AutoModelForSequenceClassification = MagicMock()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    import mem0.reranker.huggingface_reranker as hf_reranker

    monkeypatch.setattr(hf_reranker, "torch", fake_torch, raising=False)
    monkeypatch.setattr(hf_reranker, "TRANSFORMERS_AVAILABLE", True, raising=False)
    return hf_reranker


def _make_reranker(module, logits):
    """Build a reranker whose model returns the given logits for every batch."""
    reranker = module.HuggingFaceReranker(
        HuggingFaceRerankerConfig(model="test-model", device="cpu", batch_size=32, normalize=True)
    )

    logits_array = np.array(logits, dtype=np.float32)
    batch_offset = {"value": 0}

    def fake_tokenizer(pairs, **kwargs):
        batch_size = len(pairs)
        inputs = {"input_ids": MagicMock(), "attention_mask": MagicMock(), "_batch_size": batch_size}
        wrapper = MagicMock()
        wrapper.to.return_value = inputs
        return wrapper

    def fake_model(**inputs):
        batch_size = inputs.get("_batch_size", len(logits_array))
        start = batch_offset["value"]
        end = start + batch_size
        batch_logits = logits_array[start:end]
        batch_offset["value"] = end
        return SimpleNamespace(logits=_FakeTensor(batch_logits.reshape(-1, 1)))

    reranker.tokenizer = MagicMock(side_effect=fake_tokenizer)
    reranker.model = MagicMock(side_effect=fake_model)
    reranker.model.eval = MagicMock()
    return reranker


class TestHuggingFaceRerankerNormalization:
    def test_single_document_uses_sigmoid_not_zero(self, mock_huggingface_reranker):
        reranker = _make_reranker(mock_huggingface_reranker, [5.0])
        docs = [{"memory": "relevant doc"}]

        result = reranker.rerank("query", docs)

        assert len(result) == 1
        assert result[0]["rerank_score"] == pytest.approx(_sigmoid(5.0), rel=1e-5)
        assert result[0]["rerank_score"] > 0.5

    def test_tied_scores_use_sigmoid_not_zero(self, mock_huggingface_reranker):
        reranker = _make_reranker(mock_huggingface_reranker, [3.0, 3.0, 3.0])
        docs = [{"memory": f"doc{i}"} for i in range(3)]

        result = reranker.rerank("query", docs)
        expected = _sigmoid(3.0)

        assert all(doc["rerank_score"] == pytest.approx(expected, rel=1e-5) for doc in result)
        assert all(doc["rerank_score"] > 0.5 for doc in result)

    def test_scores_are_absolute_not_set_relative(self, mock_huggingface_reranker):
        """Lowest-ranked doc keeps its sigmoid score; it is not forced to 0.0."""
        reranker = _make_reranker(mock_huggingface_reranker, [8.0, 2.0])
        docs = [{"memory": "high"}, {"memory": "low"}]

        result = reranker.rerank("query", docs)

        assert result[0]["rerank_score"] == pytest.approx(_sigmoid(8.0), rel=1e-5)
        assert result[1]["rerank_score"] == pytest.approx(_sigmoid(2.0), rel=1e-5)
        assert result[1]["rerank_score"] > 0.0

    def test_normalize_false_returns_raw_logits(self, mock_huggingface_reranker):
        reranker = _make_reranker(mock_huggingface_reranker, [4.5])
        reranker.config.normalize = False
        docs = [{"memory": "doc"}]

        result = reranker.rerank("query", docs)

        assert result[0]["rerank_score"] == pytest.approx(4.5)
