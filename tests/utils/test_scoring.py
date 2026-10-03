import pytest

from mem0.utils.scoring import (
    _parse_timestamp,
    get_bm25_params,
    normalize_bm25,
    score_and_rank,
    ENTITY_BOOST_WEIGHT,
    RECENCY_WEIGHT,
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


class TestRecencyWeight:
    def test_weight_value(self):
        # Conservative default: recency can contribute at most
        # 0.1 / 1.1 of the final score -- enough to surface newer memories
        # in close calls, not enough to override clearly more relevant ones.
        assert RECENCY_WEIGHT == 0.1


def _memory(mem_id, score, created_at, updated_at=None):
    payload = {"data": f"mem {mem_id}", "created_at": created_at}
    if updated_at is not None:
        payload["updated_at"] = updated_at
    return {"id": mem_id, "score": score, "payload": payload}


class TestParseTimestamp:
    def test_iso_with_timezone(self):
        assert _parse_timestamp("2023-07-20T09:00:00+00:00") == pytest.approx(1689843600.0)

    def test_iso_z_suffix(self):
        # fromisoformat on Python 3.9 does not accept "Z".
        assert _parse_timestamp("2023-07-20T09:00:00Z") == pytest.approx(1689843600.0)

    def test_iso_naive_assumed_utc(self):
        assert _parse_timestamp("2023-07-20T09:00:00") == pytest.approx(1689843600.0)

    def test_datetime_objects(self):
        from datetime import datetime, timezone

        aware = datetime(2023, 7, 20, 9, 0, 0, tzinfo=timezone.utc)
        naive = datetime(2023, 7, 20, 9, 0, 0)
        assert _parse_timestamp(aware) == pytest.approx(1689843600.0)
        assert _parse_timestamp(naive) == pytest.approx(1689843600.0)

    def test_epoch_numbers(self):
        assert _parse_timestamp(1689843600) == pytest.approx(1689843600.0)
        assert _parse_timestamp(1689843600.5) == pytest.approx(1689843600.5)

    @pytest.mark.parametrize("bad", [None, "", "   ", "not-a-date", float("nan"), True, object()])
    def test_unparseable_returns_none(self, bad):
        assert _parse_timestamp(bad) is None


class TestRecencyScoring:
    def test_disabled_by_default_outdated_wins(self):
        """Regression for #7535: without recency, the outdated memory wins."""
        results = [
            _memory("old", 0.650003, "2023-01-18T09:00:00+00:00", "2023-01-18T09:00:00+00:00"),
            _memory("new", 0.646012, "2023-07-20T09:00:00+00:00", "2023-07-20T09:00:00+00:00"),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert scored[0]["id"] == "old"  # bug behavior, preserved when disabled

    def test_newer_update_outranks_outdated(self):
        """With recency enabled, the newer update ranks first (#7535)."""
        results = [
            _memory("old", 0.650003, "2023-01-18T09:00:00+00:00", "2023-01-18T09:00:00+00:00"),
            _memory("new", 0.646012, "2023-07-20T09:00:00+00:00", "2023-07-20T09:00:00+00:00"),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1)
        assert scored[0]["id"] == "new"
        assert scored[1]["id"] == "old"
        # new: (0.646012 + 0.1 * 1.0) / 1.1 ; old: (0.650003 + 0.1 * 0.0) / 1.1
        assert scored[0]["score"] == pytest.approx(0.746012 / 1.1)
        assert scored[1]["score"] == pytest.approx(0.650003 / 1.1)

    def test_recency_min_max_normalized(self):
        results = [
            _memory("oldest", 0.5, "2021-01-01T00:00:00+00:00"),
            _memory("middle", 0.5, "2022-01-01T00:00:00+00:00"),
            _memory("newest", 0.5, "2023-01-01T00:00:00+00:00"),
        ]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        by_id = {r["id"]: r for r in scored}
        assert by_id["oldest"]["score_details"]["recency_score"] == pytest.approx(0.0)
        assert by_id["middle"]["score_details"]["recency_score"] == pytest.approx(0.5)
        assert by_id["newest"]["score_details"]["recency_score"] == pytest.approx(1.0)
        assert [r["id"] for r in scored] == ["newest", "middle", "oldest"]

    def test_no_timestamps_recency_stays_inactive(self):
        """Weight > 0 but no parseable timestamps: scores identical to weight 0."""
        results = [
            {"id": "a", "score": 0.8, "payload": {"data": "mem a"}},
            {"id": "b", "score": 0.6, "payload": {"data": "mem b"}},
        ]
        with_weight = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.5)
        without = score_and_rank(results, {}, {}, threshold=0.1, top_k=10)
        assert [r["score"] for r in with_weight] == [r["score"] for r in without]

    def test_missing_timestamp_scores_zero(self):
        results = [
            _memory("old", 0.5, "2020-01-01T00:00:00+00:00"),
            {"id": "new", "score": 0.5, "payload": {"data": "no timestamps here"}},
        ]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        by_id = {r["id"]: r for r in scored}
        # Only one timestamp: span is 0, so the dated candidate is "newest".
        assert by_id["old"]["score_details"]["recency_score"] == pytest.approx(1.0)
        assert by_id["new"]["score_details"]["recency_score"] == pytest.approx(0.0)

    def test_updated_at_takes_precedence_over_created_at(self):
        results = [
            _memory("a", 0.5, "2024-01-01T00:00:00+00:00", "2020-06-01T00:00:00+00:00"),
            _memory("b", 0.5, "2020-01-01T00:00:00+00:00", "2024-06-01T00:00:00+00:00"),
        ]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        by_id = {r["id"]: r for r in scored}
        # b was updated more recently, even though it was created earlier.
        assert by_id["b"]["score_details"]["recency_score"] == pytest.approx(1.0)
        assert by_id["a"]["score_details"]["recency_score"] == pytest.approx(0.0)

    def test_identical_timestamps_preserve_order(self):
        results = [
            _memory("a", 0.8, "2023-01-01T00:00:00+00:00"),
            _memory("b", 0.6, "2023-01-01T00:00:00+00:00"),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1)
        assert [r["id"] for r in scored] == ["a", "b"]  # no spread: order unchanged

    def test_unparseable_timestamps_treated_as_missing(self):
        results = [
            _memory("old", 0.5, "2020-01-01T00:00:00+00:00"),
            _memory("weird", 0.5, "not-a-date"),
        ]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        by_id = {r["id"]: r for r in scored}
        assert by_id["weird"]["score_details"]["recency_score"] == pytest.approx(0.0)

    def test_divisor_includes_recency_with_all_signals(self):
        results = [_memory("a", 0.8, "2024-01-01T00:00:00+00:00")]
        bm25 = {"a": 0.6}
        entity = {"a": 0.3}
        scored = score_and_rank(results, bm25, entity, threshold=0.1, top_k=10, recency_weight=0.2)
        # max_possible = 2.5 + 0.2 = 2.7; single timestamp -> recency 1.0
        assert scored[0]["score"] == pytest.approx((0.8 + 0.6 + 0.3 + 0.2) / 2.7)

    def test_threshold_applies_before_recency_normalization(self):
        """A below-threshold candidate must not distort the recency scale."""
        results = [
            _memory("x", 0.9, "2020-01-01T00:00:00+00:00"),
            _memory("y", 0.85, "2024-01-01T00:00:00+00:00"),
            _memory("z", 0.05, "2030-01-01T00:00:00+00:00"),  # below threshold
        ]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        assert [r["id"] for r in scored] == ["y", "x"]
        by_id = {r["id"]: r for r in scored}
        # Normalized over {x, y} only: y is the newest -> 1.0, not 0.4.
        assert by_id["y"]["score_details"]["recency_score"] == pytest.approx(1.0)
        assert by_id["x"]["score_details"]["recency_score"] == pytest.approx(0.0)

    def test_much_more_relevant_older_memory_still_wins(self):
        """Recency is a nudge, not a veto: a clearly more relevant older memory keeps its rank."""
        results = [
            _memory("old", 0.9, "2020-01-01T00:00:00+00:00"),
            _memory("new", 0.5, "2024-01-01T00:00:00+00:00"),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1)
        assert scored[0]["id"] == "old"

    def test_negative_weight_disables_recency(self):
        results = [
            _memory("old", 0.650003, "2023-01-18T09:00:00+00:00"),
            _memory("new", 0.646012, "2023-07-20T09:00:00+00:00"),
        ]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, recency_weight=-1.0)
        assert scored[0]["id"] == "old"  # same as disabled
        assert scored[0]["score"] == pytest.approx(0.650003)

    def test_explain_includes_recency_when_active(self):
        results = [_memory("a", 0.8, "2024-01-01T00:00:00+00:00")]
        scored = score_and_rank(
            results, {}, {}, threshold=0.1, top_k=10, recency_weight=0.1, explain=True
        )
        details = scored[0]["score_details"]
        assert details["recency_score"] == pytest.approx(1.0)
        assert details["recency_weight"] == pytest.approx(0.1)
        assert details["max_possible_score"] == pytest.approx(1.1)

    def test_explain_omits_recency_when_inactive(self):
        results = [_memory("a", 0.8, "2024-01-01T00:00:00+00:00")]
        scored = score_and_rank(results, {}, {}, threshold=0.1, top_k=10, explain=True)
        assert "recency_score" not in scored[0]["score_details"]
        assert "recency_weight" not in scored[0]["score_details"]
