"""Regression test for reranker fallback mutating input documents."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.reranker.cohere_reranker import CohereReranker
from mem0.reranker.huggingface_reranker import HuggingFaceReranker
from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker
from mem0.reranker.zero_entropy_reranker import ZeroEntropyReranker


def _cohere_reranker():
    reranker = CohereReranker.__new__(CohereReranker)
    reranker.config = SimpleNamespace(top_k=None, return_documents=False, max_chunks_per_doc=None)
    reranker.model = "rerank-model"
    reranker.client = MagicMock()
    reranker.client.rerank.side_effect = RuntimeError("provider error")
    return reranker


def _huggingface_reranker():
    reranker = HuggingFaceReranker.__new__(HuggingFaceReranker)
    reranker.config = SimpleNamespace(top_k=None, batch_size=32, max_length=512, normalize=True)
    reranker.device = "cpu"
    reranker.tokenizer = MagicMock(side_effect=RuntimeError("tokenizer error"))
    return reranker


def _sentence_transformer_reranker():
    reranker = SentenceTransformerReranker.__new__(SentenceTransformerReranker)
    reranker.config = SimpleNamespace(top_k=None, batch_size=32, show_progress_bar=False)
    reranker.model = MagicMock()
    reranker.model.predict.side_effect = RuntimeError("model error")
    return reranker


def _zero_entropy_reranker():
    reranker = ZeroEntropyReranker.__new__(ZeroEntropyReranker)
    reranker.config = SimpleNamespace(top_k=None)
    reranker.model = "rerank-model"
    reranker.client = MagicMock()
    reranker.client.models.rerank.side_effect = RuntimeError("provider error")
    return reranker


@pytest.mark.parametrize(
    "reranker_factory",
    [_cohere_reranker, _huggingface_reranker, _sentence_transformer_reranker, _zero_entropy_reranker],
)
def test_issue_6362(reranker_factory):
    documents = [{"memory": "alpha", "score": 0.9}]

    result = reranker_factory().rerank("query", documents)

    assert result == [{"memory": "alpha", "score": 0.9, "rerank_score": 0.0}]
    assert result[0] is not documents[0]
    assert documents == [{"memory": "alpha", "score": 0.9}]
