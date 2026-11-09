"""Reranker failures must be logged, not silently swallowed.

Uses the LLMReranker because it is constructible without heavy ML deps (the
``mock_llm`` fixture stubs the LLM factory). The fix under test is shared by all
reranker providers: the ``except`` fallback now emits a ``logger.warning`` before
degrading to the original order / a neutral score.
"""

import logging

from mem0.reranker.llm_reranker import LLMReranker


class TestRerankerFailureLogging:
    def test_llm_failure_is_logged_and_falls_back(self, mock_llm, caplog):
        _factory, llm_instance = mock_llm
        llm_instance.generate_response.side_effect = RuntimeError("upstream 500")

        reranker = LLMReranker({"provider": "openai"})
        docs = [{"memory": "alpha"}, {"memory": "beta"}]

        with caplog.at_level(logging.WARNING, logger="mem0.reranker.llm_reranker"):
            result = reranker.rerank("q", docs)

        # Graceful degradation preserved: every doc still comes back, scored neutral.
        assert len(result) == 2
        assert all(d["rerank_score"] == 0.5 for d in result)

        # The failure is no longer silent.
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "expected a warning to be logged on reranking failure"
        assert "upstream 500" in caplog.text
