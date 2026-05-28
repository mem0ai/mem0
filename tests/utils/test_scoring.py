import pytest

from mem0.utils.scoring import (
    get_bm25_params,
    normalize_bm25,
    score_and_rank,
    ENTITY_BOOST_WEIGHT,
)


class TestGetBm25Params:
    def test_short_query(self):
        midpoint, steepness = get_bm25_params("hello world", lemmatized="hello world")
        assert midpoint == 5.0
        assert steepness == 0.7

    def test_medium_query(self):
        midpoint, steepness = get_bm25_params("x", lemmatized="one two three four five")
        assert midpoint == 7.0
        assert steepness == 0.6

    def test_long_query(self):
        words = " ".join(f"word{i}" for i in range(20))
        midpoint, steepness = get_bm25_params("x", lemmatized=words)
        assert midpoint == 12.0
        assert steepness == 0.5

    def test_empty_lemmatized(self):
        midpoint, steepness = get_bm25_params("test", lemmatized="")
        # Empty string -> 1 term -> short query params
        assert midpoint == 5.0


class TestNormalizeBm25:
    def test_at_midpoint(self):
        score = normalize_bm25(5.0, 5.0, 0.7)
        assert abs(score - 0.5) < 0.01  # Should be ~0.5 at midpoint

    def test_high_score(self):
        score = normalize_bm25(20.0, 5.0, 0.7)
        assert score > 0.99  # Well above midpoint

    def test_low_score(self):
        score = normalize_bm25(0.0, 5.0, 0.7)
        assert score < 0.05  # Well below midpoint

    def test_range(self):
        for raw in [0, 1, 5, 10, 20, 50]:
            score = normalize_bm25(float(raw), 5.0, 0.7)
            assert 0.0 <= score <= 1.0


class TestScoreAndRank:
    def test_semantic_only(self):
        results = [
            {"id": "a", "score": 0.9, "payload": {"data": "mem a"}},
            {"id": "b", "score": 0.5, "payload": {"data": "mem b"}},
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert len(scored) == 2
        # With no BM25/entity, max_possible=1.0, so scores stay the same
        assert scored[0]["score"] == pytest.approx(0.9)
        assert scored[1]["score"] == pytest.approx(0.5)

    def test_semantic_plus_bm25(self):
        results = [
            {"id": "a", "score": 0.8, "payload": {"data": "mem a"}},
            {"id": "b", "score": 0.6, "payload": {"data": "mem b"}},
        ]
        bm25 = {"a": 0.3, "b": 0.9}
        scored = score_and_rank(results, bm25, {}, threshold=0.1, top_k=10)
        # max_possible = 2.0 (semantic + bm25)
        # a: (0.8 + 0.3) / 2.0 = 0.55
        # b: (0.6 + 0.9) / 2.0 = 0.75
        assert scored[0]["id"] == "b"  # b should rank higher due to BM25
        assert scored[0]["score"] == pytest.approx(0.75)
        assert scored[1]["id"] == "a"
        assert scored[1]["score"] == pytest.approx(0.55)

    def test_all_three_signals(self):
        results = [{"id": "a", "score": 0.8, "payload": {"data": "mem a"}}]
        bm25 = {"a": 0.6}
        entity = {"a": 0.3}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10)
        # max_possible = 2.5
        expected = (0.8 + 0.6 + 0.3) / 2.5
        assert scored[0]["score"] == pytest.approx(expected)

    def test_threshold_gates_on_semantic(self):
        results = [
            {"id": "a", "score": 0.05, "payload": {"data": "mem a"}},  # Below threshold
            {"id": "b", "score": 0.5, "payload": {"data": "mem b"}},
        ]
        bm25 = {"a": 0.99}  # High BM25 shouldn't save it
        scored = score_and_rank(results, bm25, {}, threshold=0.1, top_k=10)
        assert len(scored) == 1
        assert scored[0]["id"] == "b"

    def test_top_k_limit(self):
        results = [{"id": str(i), "score": 0.5, "payload": {}} for i in range(20)]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=5)
        assert len(scored) == 5

    def test_adaptive_divisor_semantic_only(self):
        results = [{"id": "a", "score": 0.8, "payload": {}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        # max_possible = 1.0 (no bm25, no entity)
        assert scored[0]["score"] == pytest.approx(0.8)

    def test_adaptive_divisor_semantic_plus_entity(self):
        results = [{"id": "a", "score": 0.8, "payload": {}}]
        entity = {"a": 0.3}
        scored = score_and_rank(results, {}, entity, threshold=0.1, top_k=10)
        # max_possible = 1.5 (semantic + entity)
        expected = (0.8 + 0.3) / 1.5
        assert scored[0]["score"] == pytest.approx(expected)

    def test_empty_results(self):
        scored = score_and_rank([], {}, {}, threshold=0.1, top_k=10)
        assert scored == []

    def test_score_clamped_to_1(self):
        results = [{"id": "a", "score": 1.0, "payload": {}}]
        bm25 = {"a": 1.0}
        entity = {"a": 0.5}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10)
        assert scored[0]["score"] <= 1.0

    # ------------------------------------------------------------------
    # Regression tests for https://github.com/mem0ai/mem0/issues/5071
    # ------------------------------------------------------------------

    def test_none_score_does_not_raise_typeerror(self):
        """score=None must be treated as 0.0, not raise TypeError.

        LangChain's similarity_search_by_vector returns Document objects without
        scores; _parse_output sets score=None.  dict.get("score", 0.0) returns
        None when the key exists with a None value, so the old code raised
        TypeError: '<' not supported between NoneType and float.
        """
        results = [{"id": "a", "score": None, "payload": {"data": "mem a"}}]
        # Must not raise — None score is treated as 0.0 (below any positive threshold)
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored == []

    def test_none_score_below_zero_threshold_is_included(self):
        """score=None treated as 0.0 passes a threshold of 0.0."""
        results = [{"id": "a", "score": None, "payload": {"data": "mem a"}}]
        scored = score_and_rank(results, {}, {}, threshold=0.0, top_k=10)
        assert len(scored) == 1
        assert scored[0]["id"] == "a"

    def test_mixed_none_and_float_scores(self):
        """Ensure results with None scores are filtered while valid ones pass."""
        results = [
            {"id": "no-score", "score": None, "payload": {}},
            {"id": "has-score", "score": 0.8, "payload": {}},
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        ids = [r["id"] for r in scored]
        assert "has-score" in ids
        assert "no-score" not in ids


class TestEntityBoostWeight:
    def test_weight_value(self):
        assert ENTITY_BOOST_WEIGHT == 0.5
