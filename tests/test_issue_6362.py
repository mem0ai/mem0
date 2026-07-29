"""Regression tests for reranker fallback result isolation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from mem0.reranker.cohere_reranker import CohereReranker
from mem0.reranker.huggingface_reranker import HuggingFaceReranker
from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker
from mem0.reranker.zero_entropy_reranker import ZeroEntropyReranker


def test_issue_6362():
    """A provider failure must not add fallback scores to input documents."""
    cohere = CohereReranker.__new__(CohereReranker)
    cohere.config = SimpleNamespace(top_k=None, return_documents=False, max_chunks_per_doc=None)
    cohere.model = "rerank-v3.5"
    cohere.client = MagicMock()
    cohere.client.rerank.side_effect = RuntimeError("upstream 500")

    huggingface = HuggingFaceReranker.__new__(HuggingFaceReranker)
    huggingface.config = SimpleNamespace(top_k=None, batch_size=32, max_length=512, normalize=True)
    huggingface.tokenizer = MagicMock(side_effect=RuntimeError("tokenizer failure"))

    sentence_transformer = SentenceTransformerReranker.__new__(SentenceTransformerReranker)
    sentence_transformer.config = SimpleNamespace(top_k=None, batch_size=32, show_progress_bar=False)
    sentence_transformer.model = MagicMock()
    sentence_transformer.model.predict.side_effect = RuntimeError("model failure")

    zero_entropy = ZeroEntropyReranker.__new__(ZeroEntropyReranker)
    zero_entropy.config = SimpleNamespace(top_k=None)
    zero_entropy.model = "zerank-1"
    zero_entropy.client = MagicMock()
    zero_entropy.client.models.rerank.side_effect = RuntimeError("upstream 500")

    for reranker in (cohere, huggingface, sentence_transformer, zero_entropy):
        documents = [{"memory": "alpha", "score": 0.9}, {"memory": "beta", "score": 0.8}]
        original_documents = [document.copy() for document in documents]

        result = reranker.rerank("query", documents)

        assert documents == original_documents
        assert [document["memory"] for document in result] == ["alpha", "beta"]
        assert all(document["rerank_score"] == 0.0 for document in result)
        assert all(result_document is not input_document for result_document, input_document in zip(result, documents))
