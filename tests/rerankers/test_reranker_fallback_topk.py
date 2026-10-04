"""Regression tests pinning that the reranker fallback path still honors ``config.top_k``."""

from mem0.configs.rerankers.cohere import CohereRerankerConfig
from mem0.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig


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
