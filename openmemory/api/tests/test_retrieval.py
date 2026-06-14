"""Unit tests for the hybrid retrieval pipeline (app.utils.retrieval)."""

from app.utils.retrieval import hybrid_search, reciprocal_rank_fusion


class FakeHit:
    def __init__(self, hid, data, score=0.0):
        self.id = hid
        self.score = score
        self.payload = {"data": data, "hash": f"h-{hid}", "created_at": 1, "updated_at": 2}


class FakeEmbedding:
    def embed(self, query, _mode):
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    def __init__(self, dense, sparse):
        self._dense = dense
        self._sparse = sparse
        self.last_filters = None

    def search(self, query, vectors, top_k, filters):
        self.last_filters = filters
        return self._dense

    def keyword_search(self, query, top_k, filters):
        return self._sparse


class FakeClient:
    def __init__(self, dense, sparse, reranker=None):
        self.embedding_model = FakeEmbedding()
        self.vector_store = FakeVectorStore(dense, sparse)
        self.reranker = reranker


class ReverseReranker:
    """Deterministic fake reranker: reverses input order, tags rerank_score."""

    def rerank(self, query, documents, top_k=None):
        out = list(reversed(documents))
        for i, doc in enumerate(out):
            doc["rerank_score"] = float(len(out) - i)
        return out[:top_k] if top_k else out


def test_rrf_fuses_and_dedupes():
    a, b, c = FakeHit("a", "A"), FakeHit("b", "B"), FakeHit("c", "C")
    # 'a' ranks top in both lists -> should win after fusion.
    fused = reciprocal_rank_fusion([[a, b], [a, c]])
    ids = [hid for hid, _, _ in fused]
    assert ids[0] == "a"
    assert set(ids) == {"a", "b", "c"}  # deduped


def test_hybrid_search_dense_only_when_no_sparse():
    client = FakeClient(dense=[FakeHit("a", "A"), FakeHit("b", "B")], sparse=None)
    results, embedding = hybrid_search(client, "q", "u1", candidate_k=10)
    assert [r["id"] for r in results] == ["a", "b"]
    assert results[0]["memory"] == "A"
    assert embedding == [0.1, 0.2, 0.3]
    # user_id must be pushed into the Qdrant filter.
    assert client.vector_store.last_filters == {"user_id": "u1"}


def test_hybrid_search_combines_dense_and_sparse():
    client = FakeClient(
        dense=[FakeHit("a", "A"), FakeHit("b", "B")],
        sparse=[FakeHit("c", "C"), FakeHit("a", "A")],
    )
    results, _ = hybrid_search(client, "q", "u1", candidate_k=10)
    ids = [r["id"] for r in results]
    assert "a" in ids and "b" in ids and "c" in ids
    assert ids[0] == "a"  # appears in both lists, highest fused score


def test_hybrid_search_applies_reranker_via_param():
    client = FakeClient(
        dense=[FakeHit("a", "A"), FakeHit("b", "B"), FakeHit("c", "C")],
        sparse=None,
    )
    # Reranker passed as a parameter (not on the client) reranks the WHOLE pool.
    results, _ = hybrid_search(client, "q", "u1", candidate_k=10, reranker=ReverseReranker())
    assert [r["id"] for r in results] == ["c", "b", "a"]
    # rerank_score is surfaced as the primary score.
    assert results[0]["score"] == results[0]["rerank_score"]


def test_hybrid_search_falls_back_to_client_reranker():
    client = FakeClient(
        dense=[FakeHit("a", "A"), FakeHit("b", "B")],
        sparse=None,
        reranker=ReverseReranker(),
    )
    results, _ = hybrid_search(client, "q", "u1", candidate_k=10)
    assert [r["id"] for r in results] == ["b", "a"]


def test_hybrid_search_returns_full_pool_for_post_acl_truncation():
    # No truncation to a page size inside hybrid_search: the caller truncates
    # after ACL/state filtering, so the full candidate pool is returned.
    client = FakeClient(
        dense=[FakeHit(str(i), str(i)) for i in range(20)],
        sparse=None,
    )
    results, _ = hybrid_search(client, "q", "u1", candidate_k=20)
    assert len(results) == 20
