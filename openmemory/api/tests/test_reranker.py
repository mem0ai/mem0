"""Unit tests for the self-hostable reranker (app.utils.reranker)."""

from app.utils.reranker import FastEmbedReranker, get_reranker, reset_reranker


class FakeEncoder:
    """Stand-in for FastEmbed TextCrossEncoder: score = length of the text."""

    def rerank(self, query, texts):
        return [float(len(t)) for t in texts]


def _reranker_with_fake():
    r = FastEmbedReranker()
    r._encoder = FakeEncoder()  # bypass lazy model load (no download)
    return r


def test_reranker_sorts_descending_and_tags_score():
    r = _reranker_with_fake()
    docs = [
        {"id": "a", "memory": "x"},
        {"id": "b", "memory": "xxxxx"},
        {"id": "c", "memory": "xx"},
    ]
    out = r.rerank("q", docs)
    assert [d["id"] for d in out] == ["b", "c", "a"]
    assert out[0]["rerank_score"] == 5.0
    assert all("rerank_score" in d for d in out)


def test_reranker_top_k_truncates():
    r = _reranker_with_fake()
    docs = [{"id": "a", "memory": "x"}, {"id": "b", "memory": "xxxxx"}]
    out = r.rerank("q", docs, top_k=1)
    assert [d["id"] for d in out] == ["b"]


def test_reranker_does_not_mutate_input():
    r = _reranker_with_fake()
    docs = [{"id": "a", "memory": "x"}]
    r.rerank("q", docs)
    assert "rerank_score" not in docs[0]  # operates on copies


def test_reranker_empty_input():
    r = _reranker_with_fake()
    assert r.rerank("q", []) == []


def test_get_reranker_disabled(monkeypatch):
    monkeypatch.setenv("RERANKER_PROVIDER", "none")
    reset_reranker()
    try:
        assert get_reranker() is None
    finally:
        reset_reranker()
