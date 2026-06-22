import pytest

from mem0.utils.scoring import (
    add_entity_boost_candidates,
    build_hybrid_candidate_map,
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

    def test_threshold_allows_bm25_rescue(self):
        results = [
            {"id": "a", "score": 0.05, "payload": {"data": "mem a"}},  # Below semantic threshold
            {"id": "b", "score": 0.5, "payload": {"data": "mem b"}},
        ]
        bm25 = {"a": 0.99}  # Strong BM25 should rescue keyword-only hit
        scored = score_and_rank(results, bm25, {}, threshold=0.1, top_k=10)
        assert len(scored) == 2
        assert any(item["id"] == "a" for item in scored)

    def test_threshold_allows_entity_rescue(self):
        results = [{"id": "a", "score": 0.05, "payload": {"data": "mem a"}}]
        entity = {"a": 0.2}
        scored = score_and_rank(results, {}, entity, threshold=0.1, top_k=10)
        assert len(scored) == 1
        assert scored[0]["id"] == "a"

    def test_threshold_excludes_weak_candidates(self):
        results = [{"id": "a", "score": 0.05, "payload": {"data": "mem a"}}]
        scored = score_and_rank(results, {"a": 0.05}, {"a": 0.05}, threshold=0.1, top_k=10)
        assert scored == []

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


class TestBuildHybridCandidateMap:
    def test_merges_keyword_only_hits(self):
        semantic = [type("Mem", (), {"id": "sem-1", "score": 0.9, "payload": {"data": "semantic"}})()]
        keyword = [
            type("Mem", (), {"id": "sem-1", "score": 8.0, "payload": {"data": "semantic"}})(),
            type("Mem", (), {"id": "kw-only", "score": 12.0, "payload": {"data": "exact match"}})(),
        ]
        candidates = build_hybrid_candidate_map(semantic, keyword)
        assert set(candidates.keys()) == {"sem-1", "kw-only"}
        assert candidates["sem-1"]["score"] == 0.9
        assert candidates["kw-only"]["score"] == 0.0
        assert candidates["kw-only"]["payload"]["data"] == "exact match"

    def test_add_entity_boost_candidates_fetches_missing_memory(self):
        candidates = {"sem-1": {"id": "sem-1", "score": 0.8, "payload": {"data": "x"}}}

        class MockVectorStore:
            def get(self, vector_id):
                if vector_id == "entity-only":
                    return type(
                        "Rec",
                        (),
                        {"payload": {"data": "entity linked", "user_id": "u1"}},
                    )()
                return None

        add_entity_boost_candidates(
            candidates,
            {"entity-only": 0.4},
            threshold=0.1,
            vector_store=MockVectorStore(),
        )
        assert "entity-only" in candidates
        assert candidates["entity-only"]["payload"]["data"] == "entity linked"
