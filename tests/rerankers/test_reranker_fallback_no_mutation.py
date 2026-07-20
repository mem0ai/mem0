"""Reranker failure fallback must not mutate caller-owned document dicts (#6362)."""

from types import SimpleNamespace
from unittest.mock import MagicMock


def _docs():
    return [
        {"memory": "alpha", "score": 0.9, "id": "a"},
        {"memory": "beta", "score": 0.8, "id": "b"},
    ]


def _check(out, docs, snapshot):
    assert docs == snapshot
    assert all("rerank_score" not in d for d in docs)
    assert len(out) >= 1
    assert all(d.get("rerank_score") == 0.0 for d in out)
    assert out[0] is not docs[0]


class TestCohereFallbackNoMutation:
    def test_provider_error_does_not_mutate_input(self):
        from mem0.reranker.cohere_reranker import CohereReranker

        reranker = CohereReranker.__new__(CohereReranker)
        reranker.config = SimpleNamespace(top_k=None, return_documents=False, max_chunks_per_doc=None)
        reranker.model = "rerank-english-v3.0"
        client = MagicMock()
        client.rerank.side_effect = RuntimeError("transient 503")
        reranker.client = client

        docs = _docs()
        snapshot = [d.copy() for d in docs]
        out = reranker.rerank("q", docs, top_k=1)
        _check(out, docs, snapshot)
        assert out[0]["memory"] == "alpha"


class TestZeroEntropyFallbackNoMutation:
    def test_provider_error_does_not_mutate_input(self):
        from mem0.reranker.zero_entropy_reranker import ZeroEntropyReranker

        reranker = ZeroEntropyReranker.__new__(ZeroEntropyReranker)
        reranker.config = SimpleNamespace(top_k=None)
        reranker.model = "zerank-1"
        client = MagicMock()
        client.models.rerank.side_effect = RuntimeError("transient 503")
        reranker.client = client

        docs = _docs()
        snapshot = [d.copy() for d in docs]
        out = reranker.rerank("q", docs, top_k=1)
        _check(out, docs, snapshot)


class TestSentenceTransformerFallbackNoMutation:
    def test_predict_error_does_not_mutate_input(self):
        from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker

        reranker = SentenceTransformerReranker.__new__(SentenceTransformerReranker)
        reranker.config = SimpleNamespace(top_k=None, show_progress_bar=False)
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("cuda OOM")
        reranker.model = mock_model

        docs = _docs()
        snapshot = [d.copy() for d in docs]
        out = reranker.rerank("q", docs, top_k=1)
        _check(out, docs, snapshot)


class TestHuggingFaceFallbackNoMutation:
    def test_tokenizer_error_does_not_mutate_input(self):
        from mem0.reranker.huggingface_reranker import HuggingFaceReranker

        reranker = HuggingFaceReranker.__new__(HuggingFaceReranker)
        reranker.config = SimpleNamespace(top_k=None, batch_size=32, max_length=512, normalize=True)
        reranker.device = "cpu"
        mock_tokenizer = MagicMock()
        mock_tokenizer.side_effect = RuntimeError("tokenizer failed")
        reranker.tokenizer = mock_tokenizer
        reranker.model = MagicMock()

        docs = _docs()
        snapshot = [d.copy() for d in docs]
        out = reranker.rerank("q", docs, top_k=1)
        _check(out, docs, snapshot)
