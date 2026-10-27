"""Behavioral coverage for opt-in fusion over the existing eligible candidates."""

import pytest
from pydantic import ValidationError

from mem0.configs.base import MemoryConfig
from mem0.utils.scoring import score_and_rank


def candidates(scores):
    return [{"id": key, "score": value, "payload": {"data": key}} for key, value in scores.items()]


def fuse(results, keyword=None, entity=None, **kwargs):
    return score_and_rank(
        results, keyword or {}, entity or {}, threshold=0.1, top_k=10, fusion_strategy="rrf", **kwargs
    )


def test_fuses_all_three_rankings_in_one_pass():
    results = candidates({"a": 0.9, "b": 0.8, "c": 0.7})
    # Semantic and keyword: a > b > c; entity: b > c > a.
    # Staged fusion would instead put b first, losing the two-channel support for a.
    fused = fuse(results, {"a": 0.9, "b": 0.8, "c": 0.7}, {"a": 0.1, "b": 0.3, "c": 0.2})
    assert [result["id"] for result in fused] == ["a", "b", "c"]
    assert fused[0]["score"] == pytest.approx(2 / 61 + 1 / 63)


def test_rank_fusion_is_invariant_to_positive_channel_rescaling():
    results = candidates({"a": 0.9, "b": 0.8, "c": 0.7})
    keyword = {"a": 0.01, "b": 0.8, "c": 0.2}
    entity = {"a": 0.3, "c": 0.1}
    original = fuse(results, keyword, entity)
    scaled = fuse(results, {key: value * 100 for key, value in keyword.items()}, entity)
    assert scaled == original


def test_ties_use_average_rank_without_input_order_advantage():
    results = candidates({"a": 0.9, "b": 0.9, "c": 0.8})
    entity = {"a": 0.3, "b": 0.3}
    forward = {item["id"]: item["score"] for item in fuse(results, entity=entity)}
    reverse = {item["id"]: item["score"] for item in fuse(list(reversed(results)), entity=entity)}
    assert forward == reverse
    assert forward["a"] == forward["b"] == pytest.approx(2 / 61.5)
    assert forward["c"] == pytest.approx(1 / 63)


def test_zero_negative_and_missing_auxiliary_signals_do_not_vote():
    results = candidates({"a": 0.9, "b": 0.8, "c": 0.7})
    fused = fuse(results, {"a": 0.0, "b": -1.0}, {"a": 0.0, "c": -0.5}, explain=True)
    for rank, item in enumerate(fused, 1):
        assert item["score"] == pytest.approx(1 / (60 + rank))
        details = item["score_details"]
        assert details["bm25_rank"] is None
        assert details["entity_rank"] is None
        assert details["bm25_contribution"] == details["entity_contribution"] == 0


def test_threshold_and_candidate_scope_are_preserved_before_ranking():
    results = candidates({"eligible": 0.8, "below_threshold": 0.05})
    fused = fuse(
        results,
        {"eligible": 0.1, "below_threshold": 0.99, "keyword_only": 1.0},
        {"below_threshold": 0.5, "entity_only": 1.0},
    )
    assert [item["id"] for item in fused] == ["eligible"]
    assert fused[0]["score"] == pytest.approx(2 / 61)


def test_limit_is_applied_after_complete_fusion():
    results = candidates({"a": 0.9, "b": 0.8, "c": 0.7})
    fused = score_and_rank(results, {"c": 0.9}, {"c": 0.5}, 0.1, 1, fusion_strategy="rrf")
    assert [item["id"] for item in fused] == ["c"]


@pytest.mark.parametrize("invalid_score", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_semantic_scores_are_excluded_before_ranking(invalid_score):
    fused = fuse(candidates({"invalid": invalid_score, "valid": 0.8}), {"invalid": 1.0}, explain=True)
    assert [item["id"] for item in fused] == ["valid"]
    assert fused[0]["score"] == pytest.approx(1 / 61)
    assert fused[0]["score_details"]["semantic_rank"] == 1


def test_configurable_rank_offset_and_explanation():
    fused = fuse(candidates({"a": 0.9}), {"a": 0.1}, {"a": 0.3}, explain=True, rrf_k=10)
    item = fused[0]
    details = item["score_details"]
    assert item["score"] == pytest.approx(3 / 11)
    assert item["payload"] == {"data": "a"}
    assert details["fusion_strategy"] == "rrf"
    assert details["rrf_k"] == 10
    assert details["semantic_rank"] == details["bm25_rank"] == details["entity_rank"] == 1
    assert sum(
        details[key] for key in ("semantic_contribution", "bm25_contribution", "entity_contribution")
    ) == pytest.approx(item["score"])
    assert details["raw_score"] == details["final_score"] == item["score"]
    assert details["max_possible_score"] == pytest.approx(3 / 11)


def test_empty_candidates_and_stable_final_ties():
    assert fuse([], {"outside": 1.0}, {"outside": 1.0}) == []
    results = candidates({"b": 0.9, "a": 0.9})
    assert [item["id"] for item in fuse(results)] == ["b", "a"]


def test_small_rank_offset_returns_raw_sum_without_clipping():
    fused = fuse(candidates({"a": 0.9}), {"a": 0.1}, {"a": 0.3}, rrf_k=1)
    assert fused[0]["score"] == pytest.approx(1.5)


def test_auxiliary_only_ids_do_not_activate_an_extra_channel():
    fused = fuse(candidates({"a": 0.9}), {"outside": 0.8}, {"outside": 0.5}, explain=True)
    assert fused[0]["score"] == pytest.approx(1 / 61)
    assert fused[0]["score_details"]["max_possible_score"] == pytest.approx(1 / 61)


def test_separate_tie_groups_get_their_own_average_rank():
    fused = fuse(candidates({"a": 0.9, "b": 0.9, "c": 0.8, "d": 0.8}), explain=True)
    assert [item["score_details"]["semantic_rank"] for item in fused] == [1.5, 1.5, 3.5, 3.5]


@pytest.mark.parametrize("offset", [0, -1, 1.5, True, "60", float("inf"), float("nan")])
def test_invalid_rank_offsets_are_rejected(offset):
    with pytest.raises(ValueError, match="positive integer"):
        fuse([], rrf_k=offset)
    with pytest.raises(ValueError, match="positive integer"):
        score_and_rank([], {}, {}, 0.1, 10, rrf_k=offset)
    with pytest.raises(ValidationError):
        MemoryConfig(rrf_k=offset)


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="fusion_strategy"):
        score_and_rank([], {}, {}, 0.1, 10, fusion_strategy="unknown")
    with pytest.raises(ValidationError):
        MemoryConfig(fusion_strategy="unknown")


def test_config_defaults_and_explicit_additive_are_backward_compatible():
    config = MemoryConfig()
    assert config.fusion_strategy == "additive"
    assert config.rrf_k == 60
    results = candidates({"a": 0.9, "b": 0.5})
    args = (results, {"b": 0.8}, {"a": 0.2}, 0.1, 10)
    default = score_and_rank(*args, explain=True)
    assert score_and_rank(*args, explain=True, fusion_strategy="additive") == default
    assert "fusion_strategy" not in default[0]["score_details"]
