"""Reranker failure fallback must not mutate the caller's documents.

The success paths of every provider ``doc.copy()`` before attaching
``rerank_score`` (and ``LLMReranker`` copies even on its per-document failure
path), but the API/model providers' ``except`` fallback used to write
``rerank_score = 0.0`` directly onto the input dicts. ``Memory.search`` passes
its live result list into ``rerank()``, so a transient provider failure
permanently stamped the caller-visible memories.

Providers are instantiated via ``object.__new__`` with stubbed attributes so
the tests run without the optional heavy dependencies (cohere, transformers,
sentence-transformers, zeroentropy) installed.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.reranker.cohere_reranker import CohereReranker
from mem0.reranker.huggingface_reranker import HuggingFaceReranker
from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker
from mem0.reranker.zero_entropy_reranker import ZeroEntropyReranker


def _make_cohere():
    reranker = object.__new__(CohereReranker)
    reranker.config = SimpleNamespace(top_k=None, return_documents=False, max_chunks_per_doc=10)
    reranker.model = "rerank-english-v3.0"
    reranker.client = MagicMock()
    reranker.client.rerank.side_effect = RuntimeError("upstream 500")
    return reranker


def _make_huggingface():
    reranker = object.__new__(HuggingFaceReranker)
    reranker.config = SimpleNamespace(top_k=None, batch_size=32, max_length=512, normalize=False)
    reranker.tokenizer = MagicMock(side_effect=RuntimeError("tokenizer exploded"))
    reranker.model = MagicMock()
    reranker.device = "cpu"
    return reranker


def _make_sentence_transformer():
    reranker = object.__new__(SentenceTransformerReranker)
    reranker.config = SimpleNamespace(top_k=None, batch_size=32, show_progress_bar=False)
    reranker.model = MagicMock()
    reranker.model.predict.side_effect = RuntimeError("predict exploded")
    return reranker


def _make_zero_entropy():
    reranker = object.__new__(ZeroEntropyReranker)
    reranker.config = SimpleNamespace(top_k=None)
    reranker.model = "zerank-1"
    reranker.client = MagicMock()
    reranker.client.models.rerank.side_effect = RuntimeError("upstream 500")
    return reranker


@pytest.mark.parametrize(
    "make_reranker",
    [_make_cohere, _make_huggingface, _make_sentence_transformer, _make_zero_entropy],
    ids=["cohere", "huggingface", "sentence_transformer", "zero_entropy"],
)
class TestFallbackDoesNotMutateInput:
    def test_input_documents_unchanged_on_failure(self, make_reranker):
        reranker = make_reranker()
        documents = [{"memory": "alpha", "score": 0.9}, {"memory": "beta", "score": 0.4}]
        originals = [doc.copy() for doc in documents]

        result = reranker.rerank("query", documents)

        # The caller's dicts must come back exactly as they went in.
        assert documents == originals
        assert all("rerank_score" not in doc for doc in documents)

        # Graceful degradation still holds: same docs, original order, neutral score.
        assert len(result) == 2
        assert [doc["memory"] for doc in result] == ["alpha", "beta"]
        assert all(doc["rerank_score"] == 0.0 for doc in result)

    def test_fallback_returns_copies(self, make_reranker):
        reranker = make_reranker()
        documents = [{"memory": "alpha", "score": 0.9}]

        result = reranker.rerank("query", documents)

        assert result[0] is not documents[0]

    def test_fallback_respects_config_top_k(self, make_reranker):
        reranker = make_reranker()
        reranker.config.top_k = 1
        documents = [{"memory": "alpha"}, {"memory": "beta"}, {"memory": "gamma"}]

        result = reranker.rerank("query", documents)

        assert len(result) == 1
        assert documents == [{"memory": "alpha"}, {"memory": "beta"}, {"memory": "gamma"}]
