"""Regression tests for the reranker fallback path honoring ``config.top_k``.

When the underlying rerank call fails, the reranker falls back to returning the
documents in their original order. That fallback must still respect the
configured ``top_k`` limit, exactly like the success path does. The HuggingFace
and SentenceTransformer rerankers already behave this way; these tests pin the
same contract for the Cohere and ZeroEntropy rerankers.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from mem0.configs.rerankers.cohere import CohereRerankerConfig
from mem0.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig


@pytest.fixture
def mock_cohere(monkeypatch):
    """Provide a fake ``cohere`` module so CohereReranker imports/constructs."""
    fake_cohere = ModuleType("cohere")
    fake_client = MagicMock()
    fake_cohere.Client = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "cohere", fake_cohere)

    import mem0.reranker.cohere_reranker as cohere_reranker

    monkeypatch.setattr(cohere_reranker, "cohere", fake_cohere, raising=False)
    monkeypatch.setattr(cohere_reranker, "COHERE_AVAILABLE", True, raising=False)
    return cohere_reranker, fake_client


@pytest.fixture
def mock_zero_entropy(monkeypatch):
    """Provide a fake ``zeroentropy`` module so ZeroEntropyReranker imports."""
    fake_module = ModuleType("zeroentropy")
    fake_client = MagicMock()
    fake_module.ZeroEntropy = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "zeroentropy", fake_module)

    import mem0.reranker.zero_entropy_reranker as zero_entropy_reranker

    monkeypatch.setattr(zero_entropy_reranker, "ZeroEntropy", fake_module.ZeroEntropy, raising=False)
    monkeypatch.setattr(zero_entropy_reranker, "ZERO_ENTROPY_AVAILABLE", True, raising=False)
    return zero_entropy_reranker, fake_client


def _docs(n):
    return [{"memory": f"doc{i}"} for i in range(n)]


class TestCohereFallbackTopK:
    def test_fallback_respects_config_top_k(self, mock_cohere):
        module, fake_client = mock_cohere
        fake_client.rerank.side_effect = RuntimeError("API error")

        reranker = module.CohereReranker(CohereRerankerConfig(api_key="test-key", top_k=2))
        result = reranker.rerank("query", _docs(5))

        assert len(result) == 2

    def test_fallback_per_call_top_k_overrides_config(self, mock_cohere):
        module, fake_client = mock_cohere
        fake_client.rerank.side_effect = RuntimeError("API error")

        reranker = module.CohereReranker(CohereRerankerConfig(api_key="test-key", top_k=4))
        result = reranker.rerank("query", _docs(5), top_k=1)

        assert len(result) == 1

    def test_fallback_returns_all_when_no_top_k(self, mock_cohere):
        module, fake_client = mock_cohere
        fake_client.rerank.side_effect = RuntimeError("API error")

        reranker = module.CohereReranker(CohereRerankerConfig(api_key="test-key"))
        result = reranker.rerank("query", _docs(5))

        assert len(result) == 5


class TestZeroEntropyFallbackTopK:
    def test_fallback_respects_config_top_k(self, mock_zero_entropy):
        module, fake_client = mock_zero_entropy
        fake_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = module.ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key", top_k=2))
        result = reranker.rerank("query", _docs(5))

        assert len(result) == 2

    def test_fallback_per_call_top_k_overrides_config(self, mock_zero_entropy):
        module, fake_client = mock_zero_entropy
        fake_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = module.ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key", top_k=4))
        result = reranker.rerank("query", _docs(5), top_k=1)

        assert len(result) == 1

    def test_fallback_returns_all_when_no_top_k(self, mock_zero_entropy):
        module, fake_client = mock_zero_entropy
        fake_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = module.ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        result = reranker.rerank("query", _docs(5))

        assert len(result) == 5
