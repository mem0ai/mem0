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

        details = scored[0]["score_details"]
        assert details == {
            "semantic_score": 0.8,
            "bm25_score": 0.6,
            "entity_boost": 0.3,
            "raw_score": pytest.approx(1.7),
            "max_possible_score": 2.5,
            "final_score": pytest.approx(0.68),
            "threshold": 0.1,
        }

    def test_score_details_are_omitted_by_default(self):
        results = [{"id": "a", "score": 0.8, "payload": {"data": "mem a"}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert "score_details" not in scored[0]


class TestEntityBoostWeight:
    def test_weight_value(self):
        assert ENTITY_BOOST_WEIGHT == 0.5


class TestBiTemporalScoring:
    def test_legacy_untracked_payload_is_valid(self):
        """Records without temporal keys remain valid by default."""
        results = [{"id": "legacy", "score": 0.8, "payload": {"data": "old memory"}}]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=5)
        assert len(scored) == 1
        assert scored[0]["id"] == "legacy"

    def test_active_only_suppresses_superseded_fact(self):
        """Active query excludes superseded facts (valid_to is not None)."""
        results = [
            {
                "id": "stale_employer",
                "score": 0.95,
                "payload": {
                    "data": "Works at Stripe",
                    "valid_from": "2024-01-01T00:00:00Z",
                    "valid_to": "2026-01-01T00:00:00Z",
                },
            },
            {
                "id": "current_employer",
                "score": 0.90,
                "payload": {
                    "data": "Works at Anthropic",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                },
            },
        ]
        # Active only (default)
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=5)
        assert len(scored) == 1
        assert scored[0]["id"] == "current_employer"

    def test_active_only_disabled_returns_both(self):
        """Disabling active_only surfaces both current and superseded facts."""
        results = [
            {
                "id": "stale_employer",
                "score": 0.95,
                "payload": {
                    "data": "Works at Stripe",
                    "valid_from": "2024-01-01T00:00:00Z",
                    "valid_to": "2026-01-01T00:00:00Z",
                },
            },
            {
                "id": "current_employer",
                "score": 0.90,
                "payload": {
                    "data": "Works at Anthropic",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                },
            },
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=5, active_only=False)
        assert len(scored) == 2
        assert scored[0]["id"] == "stale_employer"
        assert scored[1]["id"] == "current_employer"

    def test_as_of_historical_reconstruction(self):
        """Querying with as_of reconstructs historical ground truth."""
        results = [
            {
                "id": "stale_employer",
                "score": 0.95,
                "payload": {
                    "data": "Works at Stripe",
                    "valid_from": "2024-01-01T00:00:00Z",
                    "valid_to": "2026-01-01T00:00:00Z",
                },
            },
            {
                "id": "current_employer",
                "score": 0.90,
                "payload": {
                    "data": "Works at Anthropic",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                },
            },
        ]
        # At mid-2025: user worked at Stripe, not yet Anthropic
        as_of_2025 = "2025-06-01T00:00:00Z"
        scored_2025 = score_and_rank(results, {}, {}, threshold=0.1, top_k=5, as_of=as_of_2025)
        assert len(scored_2025) == 1
        assert scored_2025[0]["id"] == "stale_employer"

        # At mid-2026: user works at Anthropic, Stripe is superseded
        as_of_2026 = "2026-06-01T00:00:00Z"
        scored_2026 = score_and_rank(results, {}, {}, threshold=0.1, top_k=5, as_of=as_of_2026)
        assert len(scored_2026) == 1
        assert scored_2026[0]["id"] == "current_employer"

        # At 2023: before user worked at Stripe
        as_of_2023 = "2023-01-01T00:00:00Z"
        scored_2023 = score_and_rank(results, {}, {}, threshold=0.1, top_k=5, as_of=as_of_2023)
        assert len(scored_2023) == 0

