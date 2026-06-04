"""Tests for cluster-aware retrieval (mem0ai/mem0#4956).

These tests are designed to run with **no external API keys**:
all embeddings and vector store interactions are mocked.
"""

from unittest.mock import MagicMock

import pytest

from mem0.memory.clustering import (
    CLUSTER_ID_KEY,
    CLUSTER_ROLE_KEY,
    CLUSTER_ROLE_PRIMARY,
    CLUSTER_ROLE_SIBLING,
    CLUSTER_SIZE_KEY,
    DEFAULT_CLUSTER_MAX_SIZE,
    DEFAULT_CLUSTER_THRESHOLD,
    DEFAULT_CLUSTER_TOP_K_MULTIPLIER,
    cluster_memories,
    cosine_similarity,
    resolve_cluster_kwargs,
)
from mem0.memory.main import AsyncMemory, Memory

# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_anti_parallel_vectors(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty_vectors_return_zero(self):
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity([1.0], []) == 0.0

    def test_zero_magnitude_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_mismatched_dims_raises(self):
        with pytest.raises(ValueError, match="different dimensions"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# resolve_cluster_kwargs
# ---------------------------------------------------------------------------


class TestResolveClusterKwargs:
    def test_defaults_when_expansion_off(self):
        # Defaults are returned even when expansion is off; validation skipped.
        result = resolve_cluster_kwargs(
            expand_clusters=False,
            cluster_threshold=None,
            cluster_top_k_multiplier=None,
            cluster_max_size=None,
        )
        assert result["threshold"] == DEFAULT_CLUSTER_THRESHOLD
        assert result["top_k_multiplier"] == DEFAULT_CLUSTER_TOP_K_MULTIPLIER
        assert result["max_cluster_size"] == DEFAULT_CLUSTER_MAX_SIZE

    def test_user_values_override_defaults(self):
        result = resolve_cluster_kwargs(
            expand_clusters=True,
            cluster_threshold=0.7,
            cluster_top_k_multiplier=4,
            cluster_max_size=10,
        )
        assert result["threshold"] == 0.7
        assert result["top_k_multiplier"] == 4
        assert result["max_cluster_size"] == 10

    def test_invalid_threshold_raises_only_when_enabled(self):
        # Bad value silently passed through when expansion is off.
        resolve_cluster_kwargs(
            expand_clusters=False,
            cluster_threshold=2.0,
            cluster_top_k_multiplier=None,
            cluster_max_size=None,
        )
        # But raises when enabled.
        with pytest.raises(ValueError, match="cluster_threshold"):
            resolve_cluster_kwargs(
                expand_clusters=True,
                cluster_threshold=2.0,
                cluster_top_k_multiplier=None,
                cluster_max_size=None,
            )

    def test_invalid_multiplier_raises(self):
        with pytest.raises(ValueError, match="cluster_top_k_multiplier"):
            resolve_cluster_kwargs(
                expand_clusters=True,
                cluster_threshold=None,
                cluster_top_k_multiplier=0,
                cluster_max_size=None,
            )

    def test_invalid_max_size_raises(self):
        with pytest.raises(ValueError, match="cluster_max_size"):
            resolve_cluster_kwargs(
                expand_clusters=True,
                cluster_threshold=None,
                cluster_top_k_multiplier=None,
                cluster_max_size=0,
            )


# ---------------------------------------------------------------------------
# cluster_memories
# ---------------------------------------------------------------------------


def _mk(memory_text: str, score: float, **extra) -> dict:
    """Build a memory result dict matching what _search_vector_store returns."""
    return {"id": memory_text, "memory": memory_text, "score": score, **extra}


def _stub_embed_batch(text_to_vec: dict[str, list[float]]):
    """Return a callable that emits the configured vector for each text."""

    def _impl(texts):
        return [text_to_vec[t] for t in texts]

    return _impl


class TestClusterMemories:
    def test_empty_input_returns_empty(self):
        result = cluster_memories(
            [],
            embed_batch=lambda _texts: [],
            top_k=10,
            threshold=0.85,
        )
        assert result == []

    def test_singleton_input_is_tagged_primary(self):
        memories = [_mk("only one", 0.9, created_at="2026-05-22")]
        result = cluster_memories(
            memories,
            embed_batch=lambda _texts: [],  # not called
            top_k=10,
            threshold=0.85,
        )
        assert len(result) == 1
        assert result[0][CLUSTER_ID_KEY] == "c0"
        assert result[0][CLUSTER_SIZE_KEY] == 1
        assert result[0][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_PRIMARY
        # Original fields preserved.
        assert result[0]["memory"] == "only one"
        assert result[0]["score"] == 0.9
        assert result[0]["created_at"] == "2026-05-22"

    def test_two_similar_items_form_one_cluster(self):
        # Both vectors are parallel -> cosine 1.0 -> always cluster together.
        memories = [
            _mk("I work at Company B", 0.92, created_at="2026-05-22"),
            _mk("I work at Company A", 0.89, created_at="2026-02-15"),
        ]
        vecs = {
            "I work at Company B": [1.0, 0.0, 0.0],
            "I work at Company A": [1.0, 0.0, 0.0],
        }
        result = cluster_memories(
            memories,
            embed_batch=_stub_embed_batch(vecs),
            top_k=10,
            threshold=0.85,
        )
        assert len(result) == 2
        assert {r[CLUSTER_ID_KEY] for r in result} == {"c0"}
        assert result[0][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_PRIMARY
        assert result[1][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_SIBLING
        # Cluster ordering matches input ordering (= score-desc).
        assert result[0]["memory"] == "I work at Company B"
        assert result[1]["memory"] == "I work at Company A"

    def test_dissimilar_items_form_separate_clusters(self):
        memories = [
            _mk("I work at B", 0.92),
            _mk("I live in NY", 0.62),
        ]
        vecs = {
            "I work at B": [1.0, 0.0],
            "I live in NY": [0.0, 1.0],  # orthogonal -> not clustered
        }
        result = cluster_memories(
            memories,
            embed_batch=_stub_embed_batch(vecs),
            top_k=10,
            threshold=0.85,
        )
        assert len(result) == 2
        assert result[0][CLUSTER_ID_KEY] == "c0"
        assert result[1][CLUSTER_ID_KEY] == "c1"
        # Each is its own primary.
        assert result[0][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_PRIMARY
        assert result[1][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_PRIMARY
        assert result[0][CLUSTER_SIZE_KEY] == 1
        assert result[1][CLUSTER_SIZE_KEY] == 1

    def test_max_cluster_size_truncates_siblings(self):
        # Four identical-embedding items; cap to 2.
        memories = [_mk(f"item-{i}", 0.9 - 0.01 * i) for i in range(4)]
        vecs = {f"item-{i}": [1.0, 0.0] for i in range(4)}
        result = cluster_memories(
            memories,
            embed_batch=_stub_embed_batch(vecs),
            top_k=10,
            threshold=0.85,
            max_cluster_size=2,
        )
        # 4 items, all want to join the same cluster, capped to 2.
        cluster_0_members = [r for r in result if r[CLUSTER_ID_KEY] == "c0"]
        assert len(cluster_0_members) == 2
        # First two highest-scoring members win; rest are dropped silently.
        assert {r["memory"] for r in cluster_0_members} == {"item-0", "item-1"}

    def test_top_k_caps_number_of_clusters(self):
        # Three orthogonal clusters; ask for only 2.
        memories = [
            _mk("A", 0.9),
            _mk("B", 0.85),
            _mk("C", 0.80),
        ]
        vecs = {
            "A": [1.0, 0.0, 0.0],
            "B": [0.0, 1.0, 0.0],
            "C": [0.0, 0.0, 1.0],
        }
        result = cluster_memories(
            memories,
            embed_batch=_stub_embed_batch(vecs),
            top_k=2,
            threshold=0.85,
        )
        cluster_ids = {r[CLUSTER_ID_KEY] for r in result}
        assert cluster_ids == {"c0", "c1"}
        # C (lowest score) is dropped because we asked for 2 clusters.
        assert all(r["memory"] != "C" for r in result)

    def test_invalid_top_k_raises(self):
        with pytest.raises(ValueError, match="top_k"):
            cluster_memories(
                [_mk("a", 0.9)],
                embed_batch=lambda _t: [[1.0]],
                top_k=0,
            )

    def test_embed_batch_failure_returns_unclustered(self, caplog):
        memories = [_mk("a", 0.9), _mk("b", 0.85)]

        def boom(_texts):
            raise RuntimeError("embedding API down")

        result = cluster_memories(memories, embed_batch=boom, top_k=10)
        # Falls back to passing through (truncated to top_k) without tags.
        assert len(result) == 2
        assert CLUSTER_ID_KEY not in result[0]

    def test_embed_batch_length_mismatch_returns_unclustered(self):
        memories = [_mk("a", 0.9), _mk("b", 0.85)]
        # Returns only one vector for two inputs — corrupted upstream.
        result = cluster_memories(
            memories,
            embed_batch=lambda _texts: [[1.0, 0.0]],
            top_k=10,
        )
        assert len(result) == 2
        assert CLUSTER_ID_KEY not in result[0]

    def test_anchor_based_avoids_transitive_chaining(self):
        # A close to B (sim 0.9), B close to C (sim 0.9), but A not close to C.
        # Pure single-link would put A, B, C in one cluster (transitive).
        # Anchor-based: only compare to first member (A). C is far from A,
        # so C gets its own cluster.
        import math

        # Construct three vectors:
        #   A = (1, 0)
        #   B = (cos(20deg), sin(20deg))    -> A·B ≈ 0.94
        #   C = (cos(50deg), sin(50deg))    -> A·C ≈ 0.64, but B·C ≈ 0.94
        a = [1.0, 0.0]
        b = [math.cos(math.radians(20)), math.sin(math.radians(20))]
        c = [math.cos(math.radians(50)), math.sin(math.radians(50))]
        memories = [_mk("A", 0.95), _mk("B", 0.90), _mk("C", 0.85)]
        result = cluster_memories(
            memories,
            embed_batch=_stub_embed_batch({"A": a, "B": b, "C": c}),
            top_k=10,
            threshold=0.85,
        )
        # A and B end up in the same cluster (anchor A, sim 0.94 >= 0.85).
        # C does NOT join A's cluster (anchor sim 0.64 < 0.85).
        cluster_map = {r["memory"]: r[CLUSTER_ID_KEY] for r in result}
        assert cluster_map["A"] == cluster_map["B"]
        assert cluster_map["C"] != cluster_map["A"]


# ---------------------------------------------------------------------------
# Memory.search end-to-end (mocked embedding + vector store)
# ---------------------------------------------------------------------------


def _make_memory(mocker, search_results):
    """Construct a `Memory` instance with the vector store / embedder mocked.

    `search_results` is the list of dicts that `_search_vector_store` will
    return. The embedder's `embed_batch` is stubbed to emit identical
    vectors for all texts (forces them into one cluster).
    """
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mocker.MagicMock())
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mocker.MagicMock(), mocker.MagicMock()],
    )
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    memory = Memory()
    memory.api_version = "v1.1"
    memory._search_vector_store = MagicMock(return_value=search_results)
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed_batch = MagicMock(side_effect=lambda texts, _action: [[1.0, 0.0] for _ in texts])
    memory.reranker = None
    return memory


class TestMemorySearchClusterExpansion:
    def test_off_by_default_returns_unmodified_results(self, mocker):
        results = [
            {"id": "1", "memory": "I work at A", "score": 0.9},
            {"id": "2", "memory": "I work at B", "score": 0.85},
        ]
        memory = _make_memory(mocker, results)

        out = memory.search("where do I work?", filters={"user_id": "u1"})

        assert out["results"] == results
        # No cluster metadata added.
        assert CLUSTER_ID_KEY not in out["results"][0]
        # Embedder.embed_batch should NOT have been called.
        memory.embedding_model.embed_batch.assert_not_called()

    def test_expand_clusters_adds_metadata(self, mocker):
        results = [
            {"id": "1", "memory": "I work at B", "score": 0.92, "created_at": "today"},
            {"id": "2", "memory": "I work at A", "score": 0.89, "created_at": "old"},
        ]
        memory = _make_memory(mocker, results)

        out = memory.search(
            "where do I work?",
            filters={"user_id": "u1"},
            expand_clusters=True,
        )

        assert len(out["results"]) == 2
        for r in out["results"]:
            assert CLUSTER_ID_KEY in r
            assert CLUSTER_SIZE_KEY in r
            assert CLUSTER_ROLE_KEY in r
        # Both went into the same cluster (mock vectors identical).
        assert out["results"][0][CLUSTER_ID_KEY] == out["results"][1][CLUSTER_ID_KEY]
        # Highest-score memory is the primary; older one is sibling.
        assert out["results"][0][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_PRIMARY
        assert out["results"][1][CLUSTER_ROLE_KEY] == CLUSTER_ROLE_SIBLING

    def test_expand_clusters_over_fetches_from_vector_store(self, mocker):
        results = [{"id": str(i), "memory": f"m-{i}", "score": 0.9 - 0.01 * i} for i in range(5)]
        memory = _make_memory(mocker, results)

        memory.search(
            "q",
            filters={"user_id": "u1"},
            top_k=2,
            expand_clusters=True,
            cluster_top_k_multiplier=4,
        )

        # _search_vector_store should have been called with limit = 2 * 4 = 8.
        # call_args.args = (query, filters, limit, threshold)
        call_args = memory._search_vector_store.call_args
        assert call_args.args[2] == 8

    def test_invalid_cluster_threshold_raises(self, mocker):
        memory = _make_memory(mocker, [])
        with pytest.raises(ValueError, match="cluster_threshold"):
            memory.search(
                "q",
                filters={"user_id": "u1"},
                expand_clusters=True,
                cluster_threshold=1.5,
            )


@pytest.mark.asyncio
class TestAsyncMemorySearchClusterExpansion:
    async def test_async_expand_clusters_adds_metadata(self, mocker):
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", mocker.MagicMock())
        mocker.patch(
            "mem0.utils.factory.VectorStoreFactory.create",
            side_effect=[mocker.MagicMock(), mocker.MagicMock()],
        )
        mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
        mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

        memory = AsyncMemory()
        memory.api_version = "v1.1"

        results = [
            {"id": "1", "memory": "I work at B", "score": 0.92},
            {"id": "2", "memory": "I work at A", "score": 0.89},
        ]

        async def _fake_search(*_args, **_kwargs):
            return results

        memory._search_vector_store = _fake_search
        memory.embedding_model = MagicMock()
        memory.embedding_model.embed_batch = MagicMock(side_effect=lambda texts, _action: [[1.0, 0.0] for _ in texts])
        memory.reranker = None

        out = await memory.search(
            "where do I work?",
            filters={"user_id": "u1"},
            expand_clusters=True,
        )

        assert len(out["results"]) == 2
        # Both clustered together (identical mock vectors).
        cluster_ids = {r[CLUSTER_ID_KEY] for r in out["results"]}
        assert len(cluster_ids) == 1
        roles = [r[CLUSTER_ROLE_KEY] for r in out["results"]]
        assert roles == [CLUSTER_ROLE_PRIMARY, CLUSTER_ROLE_SIBLING]
