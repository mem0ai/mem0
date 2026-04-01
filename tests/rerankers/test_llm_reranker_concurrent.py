"""Tests for LLMReranker concurrent scoring (max_workers > 1).

Covers:
- max_workers=1 default (sequential, existing behaviour unchanged)
- max_workers>1 parallel path (all docs scored, order preserved by score)
- max_workers capped at len(documents) to avoid creating excess threads
- Concurrent path still applies top_k correctly
- Individual worker failure falls back to 0.5 without crashing the batch
- Original documents are never mutated
- Config field accepted and validated
"""

from concurrent.futures import Future
from unittest.mock import MagicMock, patch

from mem0.configs.rerankers.llm import LLMRerankerConfig
from mem0.reranker.llm_reranker import LLMReranker


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestMaxWorkersConfig:
    def test_default_max_workers_is_1(self):
        config = LLMRerankerConfig()
        assert config.max_workers == 1

    def test_custom_max_workers_accepted(self):
        config = LLMRerankerConfig(max_workers=4)
        assert config.max_workers == 4

    def test_max_workers_passed_through_dict_config(self, mock_llm):
        reranker = LLMReranker({"provider": "openai", "max_workers": 8})
        assert reranker.config.max_workers == 8


# ---------------------------------------------------------------------------
# Sequential path (max_workers=1, default)
# ---------------------------------------------------------------------------

class TestSequentialRerank:
    """Ensures the default sequential path is unchanged."""

    def test_sequential_scores_all_docs(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = ["0.9", "0.2", "0.6"]

        reranker = LLMReranker({"provider": "openai"})  # max_workers defaults to 1
        docs = [{"memory": "a"}, {"memory": "b"}, {"memory": "c"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 3
        assert result[0]["rerank_score"] == 0.9
        assert result[1]["rerank_score"] == 0.6
        assert result[2]["rerank_score"] == 0.2

    def test_sequential_calls_llm_n_times(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.5"

        reranker = LLMReranker({"provider": "openai"})
        docs = [{"memory": f"doc{i}"} for i in range(5)]
        reranker.rerank("query", docs)

        assert mock_llm_instance.generate_response.call_count == 5


# ---------------------------------------------------------------------------
# Concurrent path (max_workers > 1)
# ---------------------------------------------------------------------------

class TestConcurrentRerank:
    def test_concurrent_returns_all_docs(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.7"

        reranker = LLMReranker({"provider": "openai", "max_workers": 4})
        docs = [{"memory": f"doc{i}"} for i in range(6)]
        result = reranker.rerank("query", docs)

        assert len(result) == 6

    def test_concurrent_sorted_by_score_descending(self, mock_llm):
        _, mock_llm_instance = mock_llm
        # Scores returned in arbitrary order (simulates concurrent completion)
        mock_llm_instance.generate_response.side_effect = ["0.3", "0.9", "0.1", "0.7"]

        reranker = LLMReranker({"provider": "openai", "max_workers": 4})
        docs = [{"memory": f"doc{i}"} for i in range(4)]
        result = reranker.rerank("query", docs)

        scores = [r["rerank_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_concurrent_top_k_applied(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.side_effect = ["0.9", "0.5", "0.1", "0.7"]

        reranker = LLMReranker({"provider": "openai", "max_workers": 4})
        docs = [{"memory": f"doc{i}"} for i in range(4)]
        result = reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2
        assert result[0]["rerank_score"] >= result[1]["rerank_score"]

    def test_max_workers_capped_at_num_documents(self, mock_llm):
        """ThreadPoolExecutor should be created with at most len(docs) workers."""
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.5"

        reranker = LLMReranker({"provider": "openai", "max_workers": 100})
        docs = [{"memory": "only two docs"}, {"memory": "doc2"}]

        with patch("mem0.reranker.llm_reranker.ThreadPoolExecutor") as mock_executor_cls:
            mock_executor_cls.return_value.__enter__ = MagicMock(return_value=MagicMock(
                submit=MagicMock(side_effect=lambda fn, *a, **kw: _make_future(fn(*a, **kw)))
            ))
            mock_executor_cls.return_value.__exit__ = MagicMock(return_value=False)
            reranker.rerank("query", docs)
            # Should be capped at 2 (len(docs)), not 100
            mock_executor_cls.assert_called_once_with(max_workers=2)

    def test_concurrent_worker_failure_falls_back_to_0_5(self, mock_llm):
        """A single worker raising an exception should not crash the whole batch."""
        _, mock_llm_instance = mock_llm
        # First call raises, second succeeds
        mock_llm_instance.generate_response.side_effect = [
            RuntimeError("API timeout"), "0.8"
        ]

        reranker = LLMReranker({"provider": "openai", "max_workers": 2})
        docs = [{"memory": "bad doc"}, {"memory": "good doc"}]
        result = reranker.rerank("query", docs)

        assert len(result) == 2
        scores = {r["memory"]: r["rerank_score"] for r in result}
        assert scores["bad doc"] == 0.5
        assert scores["good doc"] == 0.8

    def test_concurrent_does_not_mutate_originals(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.8"

        reranker = LLMReranker({"provider": "openai", "max_workers": 3})
        originals = [{"memory": f"doc{i}", "id": str(i)} for i in range(3)]
        reranker.rerank("query", originals)

        for doc in originals:
            assert "rerank_score" not in doc


# ---------------------------------------------------------------------------
# Edge cases common to both paths
# ---------------------------------------------------------------------------

class TestRerankEdgeCases:
    def test_empty_documents_returns_empty(self, mock_llm):
        reranker = LLMReranker({"provider": "openai", "max_workers": 4})
        assert reranker.rerank("query", []) == []

    def test_single_document_concurrent(self, mock_llm):
        _, mock_llm_instance = mock_llm
        mock_llm_instance.generate_response.return_value = "0.6"

        reranker = LLMReranker({"provider": "openai", "max_workers": 4})
        result = reranker.rerank("query", [{"memory": "solo doc"}])

        assert len(result) == 1
        assert result[0]["rerank_score"] == 0.6


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_future(result):
    """Create a resolved Future for mocking ThreadPoolExecutor.submit."""
    f = Future()
    f.set_result(result)
    return f
