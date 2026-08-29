from datetime import datetime, timedelta, timezone

import pytest

from mem0.utils.scoring import (
    ENTITY_BOOST_WEIGHT,
    RECENCY_HALF_LIFE_DAYS,
    W_BM25,
    W_ENTITY,
    W_RECENCY,
    W_SEMANTIC,
    get_bm25_params,
    normalize_bm25,
    score_and_rank,
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
        assert scored[0]["score"] == pytest.approx(W_SEMANTIC * 0.9)
        assert scored[1]["score"] == pytest.approx(W_SEMANTIC * 0.5)

    def test_semantic_plus_bm25(self):
        results = [
            {"id": "a", "score": 0.8, "payload": {"data": "mem a"}},
            {"id": "b", "score": 0.6, "payload": {"data": "mem b"}},
        ]
        bm25 = {"a": 0.3, "b": 0.9}
        scored = score_and_rank(results, bm25, {}, threshold=0.1, top_k=10)
        assert scored[0]["id"] == "b"  # b should rank higher due to BM25
        assert scored[0]["score"] == pytest.approx(W_SEMANTIC * 0.6 + W_BM25 * 0.9)
        assert scored[1]["id"] == "a"
        assert scored[1]["score"] == pytest.approx(W_SEMANTIC * 0.8 + W_BM25 * 0.3)

    def test_all_three_signals(self):
        results = [{"id": "a", "score": 0.8, "payload": {"data": "mem a"}}]
        bm25 = {"a": 0.6}
        entity = {"a": 0.3}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10)
        expected = W_SEMANTIC * 0.8 + W_BM25 * 0.6 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT)
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

    def test_missing_signals_contribute_zero(self):
        results = [{"id": "a", "score": 0.8, "payload": {}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored[0]["score"] == pytest.approx(W_SEMANTIC * 0.8)

    def test_semantic_plus_entity(self):
        results = [{"id": "a", "score": 0.8, "payload": {}}]
        entity = {"a": 0.3}
        scored = score_and_rank(results, {}, entity, threshold=0.1, top_k=10)
        expected = W_SEMANTIC * 0.8 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT)
        assert scored[0]["score"] == pytest.approx(expected)

    def test_empty_results(self):
        scored = score_and_rank([], {}, {}, threshold=0.1, top_k=10)
        assert scored == []

    def test_none_score_treated_as_zero(self):
        """Defensive: score=None must not crash on None < threshold comparison."""
        results = [{"id": "a", "score": None, "payload": {"data": "mem a"}}]
        # Should not raise TypeError; None score is treated as 0.0 and filtered out
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored == []

    def test_score_clamped_to_1(self):
        results = [{"id": "a", "score": 1.0, "payload": {}}]
        bm25 = {"a": 1.0}
        entity = {"a": 0.5}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10)
        assert scored[0]["score"] <= 1.0

    def test_explain_includes_score_details(self):
        results = [{"id": "a", "score": 0.8, "payload": {"data": "mem a"}}]
        bm25 = {"a": 0.6}
        entity = {"a": 0.3}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10, explain=True)

        expected = W_SEMANTIC * 0.8 + W_BM25 * 0.6 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT)
        details = scored[0]["score_details"]
        assert details == {
            "semantic_score": 0.8,
            "bm25_score": 0.6,
            "entity_boost": 0.3,
            "recency_score": 0.0,  # no timestamp on this payload
            "weights": {
                "semantic": W_SEMANTIC,
                "bm25": W_BM25,
                "entity": W_ENTITY,
                "recency": W_RECENCY,
            },
            "final_score": pytest.approx(expected),
            "threshold": 0.1,
        }

    def test_score_details_are_omitted_by_default(self):
        results = [{"id": "a", "score": 0.8, "payload": {"data": "mem a"}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert "score_details" not in scored[0]


class TestScoreComparability:
    """A candidate's score must depend only on that candidate's own signals.

    Regression: the divisor was chosen from whether ANY candidate in the batch
    had a BM25 or entity signal, so an unrelated memory matching keywords
    silently rescaled everyone else's score and made cross-query thresholds
    meaningless.
    """

    def test_score_unchanged_when_another_candidate_matches_keywords(self):
        results = [
            {"id": "a", "score": 0.92, "payload": {}},
            {"id": "b", "score": 0.41, "payload": {}},
        ]
        alone = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        with_bm25_on_b = score_and_rank(results, {"b": 0.9}, {}, threshold=0.1, top_k=10)

        score_of = lambda scored: {s["id"]: s["score"] for s in scored}  # noqa: E731
        assert score_of(alone)["a"] == pytest.approx(score_of(with_bm25_on_b)["a"])

    def test_weights_sum_to_one_so_scores_stay_in_range(self):
        assert W_SEMANTIC + W_BM25 + W_ENTITY + W_RECENCY == pytest.approx(1.0)


class TestKeywordOnlyCandidates:
    """A BM25 hit outside the semantic top-N must still be rankable.

    The semantic threshold describes a score we actually measured. A
    keyword-only candidate never got one, so gating it on a placeholder 0.0
    silently discarded every exact-term match that embedded poorly.
    """

    def test_keyword_only_candidate_survives_semantic_threshold(self):
        results = [
            {"id": "a", "score": 0.5, "payload": {"data": "mem a"}},
            {"id": "b", "score": 0.0, "keyword_only": True, "payload": {"data": "mem b"}},
        ]
        scored = score_and_rank(results, {"b": 0.9}, {}, threshold=0.1, top_k=10)
        assert "b" in [s["id"] for s in scored]

    def test_keyword_only_candidate_is_not_penalized_for_its_missing_signal(self):
        """A strong keyword match must not lose on weight it could never earn.

        Regression: a keyword-only row scored 0.3 * bm25 against the full
        1.0 scale, so a near-perfect term match capped at 0.30 and lost to any
        mediocre semantic hit, re-burying the recall it was added to surface.
        """
        results = [
            {"id": "a", "score": 0.5, "payload": {}},
            {"id": "b", "score": 0.0, "keyword_only": True, "payload": {}},
        ]
        scored = score_and_rank(results, {"b": 0.99}, {}, threshold=0.1, top_k=10)

        assert [s["id"] for s in scored] == ["b", "a"]
        assert scored[0]["score"] == pytest.approx(
            W_BM25 * 0.99 / (W_BM25 + W_ENTITY + W_RECENCY)
        )

    def test_keyword_only_candidate_gated_on_its_own_bm25_score(self):
        results = [{"id": "b", "score": 0.0, "keyword_only": True, "payload": {"data": "mem b"}}]
        scored = score_and_rank(results, {"b": 0.05}, {}, threshold=0.1, top_k=10)
        assert scored == []


class TestRecency:
    """Ranking must know that a memory has an age.

    Regression: created_at was stored on every memory and never read, so a
    preference stated two years ago outranked last week's correction whenever
    it embedded fractionally better.
    """

    @staticmethod
    def _aged(mem_id, days, score=0.8):
        created = datetime.now(timezone.utc) - timedelta(days=days)
        return {"id": mem_id, "score": score, "payload": {"created_at": created.isoformat()}}

    def test_newer_memory_wins_when_relevance_ties(self):
        results = [self._aged("old", 730), self._aged("new", 1)]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert [s["id"] for s in scored] == ["new", "old"]

    def test_decay_halves_at_the_half_life(self):
        fresh = score_and_rank([self._aged("a", 0)], {}, {}, threshold=0.1, top_k=1)
        aged = score_and_rank(
            [self._aged("a", RECENCY_HALF_LIFE_DAYS)], {}, {}, threshold=0.1, top_k=1
        )
        recency_of = lambda s: s[0]["score"] - W_SEMANTIC * 0.8  # noqa: E731
        assert recency_of(aged) == pytest.approx(recency_of(fresh) / 2, rel=1e-3)

    def test_recency_cannot_outweigh_relevance(self):
        results = [
            {"id": "relevant", "score": 0.9, "payload": {}},
            self._aged("fresh_but_vague", 0, score=0.2),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored[0]["id"] == "relevant"

    def test_missing_timestamp_earns_no_recency_credit(self):
        results = [{"id": "a", "score": 0.8, "payload": {}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored[0]["score"] == pytest.approx(W_SEMANTIC * 0.8)

    def test_unparseable_timestamp_does_not_raise(self):
        results = [{"id": "a", "score": 0.8, "payload": {"created_at": "last tuesday"}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored[0]["score"] == pytest.approx(W_SEMANTIC * 0.8)

    def test_updated_at_takes_precedence_over_created_at(self):
        old = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        results = [
            {"id": "a", "score": 0.8, "payload": {"created_at": old, "updated_at": recent}},
            {"id": "b", "score": 0.8, "payload": {"created_at": old}},
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert [s["id"] for s in scored] == ["a", "b"]


class TestEntityBoostWeight:
    def test_weight_value(self):
        assert ENTITY_BOOST_WEIGHT == 0.5
