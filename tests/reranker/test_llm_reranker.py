import math
from typing import Any, Dict, List

import pytest

from mem0.configs.rerankers.llm import LLMRerankerConfig
from mem0.reranker.llm_reranker import LLMReranker


class DummyLLM:
    """
    Minimal fake LLM returning deterministic numeric strings based on prompt content.
    This allows testing reranking logic without external API calls.
    """

    def __init__(self, score_map: Dict[str, float]):
        self.score_map = score_map
        self.calls: List[Dict[str, Any]] = []

    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        content = messages[-1]["content"]
        self.calls.append({"content": content})

        for key, score in self.score_map.items():
            if key in content:
                return str(score)

        return "0.5"


def _make_docs() -> List[Dict[str, Any]]:
    return [
        {"id": "1", "memory": "doc0 about cats"},
        {"id": "2", "memory": "doc1 about dogs"},
        {"id": "3", "memory": "doc2 about horses"},
    ]


def _make_reranker(*, max_concurrency=None, top_k=2, monkeypatch=None) -> LLMReranker:
    cfg = LLMRerankerConfig(
        model="dummy-model",
        provider="openai",
        top_k=top_k,
        max_concurrency=max_concurrency,
    )
    dummy_llm = DummyLLM({"doc0": 0.1, "doc1": 0.5, "doc2": 0.9})

    # LLMReranker.__init__ always calls LlmFactory.create; patch it to avoid real providers/network.
    if monkeypatch is not None:
        from mem0.reranker import llm_reranker as llm_reranker_module

        monkeypatch.setattr(llm_reranker_module.LlmFactory, "create", lambda *args, **kwargs: dummy_llm)

    reranker = LLMReranker(cfg)
    # Ensure the instance uses our dummy (in case future init changes)
    reranker.llm = dummy_llm
    return reranker


@pytest.mark.parametrize("max_concurrency", [None, 1])
def test_rerank_sequential_path_preserves_behavior(max_concurrency, monkeypatch):
    reranker = _make_reranker(max_concurrency=max_concurrency, top_k=2, monkeypatch=monkeypatch)
    docs = _make_docs()

    result = reranker.rerank("pets", docs, top_k=2)

    assert len(result) == 2
    scores = [d["rerank_score"] for d in result]
    assert scores == sorted(scores, reverse=True)

    # Expected order: doc2 (0.9), doc1 (0.5)
    assert [d["id"] for d in result] == ["3", "2"]

    # One LLM call per document
    assert len(reranker.llm.calls) == len(docs)


def test_rerank_concurrent_path_matches_sequential_results():
    docs = _make_docs()

    # Use separate monkeypatch instances per reranker to avoid sharing call history.
    from _pytest.monkeypatch import MonkeyPatch

    seq_mp = MonkeyPatch()
    seq = _make_reranker(max_concurrency=None, top_k=2, monkeypatch=seq_mp)
    seq_result = seq.rerank("pets", docs, top_k=2)
    seq_ids = [d["id"] for d in seq_result]
    seq_scores = [d["rerank_score"] for d in seq_result]
    seq_mp.undo()

    conc_mp = MonkeyPatch()
    conc = _make_reranker(max_concurrency=4, top_k=2, monkeypatch=conc_mp)
    conc_result = conc.rerank("pets", docs, top_k=2)
    conc_ids = [d["id"] for d in conc_result]
    conc_scores = [d["rerank_score"] for d in conc_result]
    conc_mp.undo()

    assert conc_ids == seq_ids
    assert len(conc_scores) == len(seq_scores)
    for a, b in zip(conc_scores, seq_scores):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)

    assert len(conc.llm.calls) == len(docs)

