"""Unit tests for 1-hop graph expansion over LLM-asserted memory links.

These tests exercise :mod:`mem0.memory.graph_expansion` with no vector store
and no LLM involvement. The three public entry points are validated:

- :func:`collect_expansion_ids` — pure dict-level neighbour collection.
- :func:`build_expanded_candidates` — scoring & shape of the candidate list.
- :func:`expand_with_links` — end-to-end orchestration with a fake fetcher.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List

import pytest

from mem0.memory.graph_expansion import (
    build_expanded_candidates,
    collect_expansion_ids,
    expand_with_links,
    make_vector_store_fetcher,
)


def _mem(mem_id: str, data: str = "dummy", **extra_payload):
    """Mimic the shape of a vector-store memory record (object with attrs)."""
    payload = {"data": data, **extra_payload}
    return SimpleNamespace(id=mem_id, payload=payload, score=None)


def _cand(mem_id: str, score: float, links=None, data: str = "seed"):
    payload = {"data": data}
    if links is not None:
        payload["linked_memory_ids"] = links
    return {"id": mem_id, "score": score, "payload": payload}


# ---------------------------------------------------------------------------
# collect_expansion_ids
# ---------------------------------------------------------------------------


class TestCollectExpansionIds:
    def test_empty_input_returns_empty(self):
        ids, scores = collect_expansion_ids([])
        assert ids == [] and scores == {}

    def test_seed_with_no_links_returns_empty(self):
        ids, scores = collect_expansion_ids([_cand("a", 0.9)])
        assert ids == [] and scores == {}

    def test_collects_links_from_top_seeds_only(self):
        """With seed_k=1, only the top seed's links are followed."""
        results = [
            _cand("a", 0.9, links=["link1"]),
            _cand("b", 0.8, links=["link2"]),  # should be ignored
        ]
        ids, scores = collect_expansion_ids(results, seed_k=1)
        assert ids == ["link1"]
        assert scores == {"link1": 0.9}

    def test_seed_score_propagated_as_best(self):
        """An expanded id linked by multiple seeds takes the max seed score."""
        results = [
            _cand("a", 0.9, links=["shared"]),
            _cand("b", 0.6, links=["shared"]),
        ]
        ids, scores = collect_expansion_ids(results, seed_k=5)
        assert ids == ["shared"]
        assert scores["shared"] == pytest.approx(0.9)

    def test_candidate_already_in_pool_is_skipped(self):
        """A seed that links to another seed must not be re-added."""
        results = [
            _cand("a", 0.9, links=["b"]),
            _cand("b", 0.5),
        ]
        ids, _ = collect_expansion_ids(results)
        assert ids == []  # "b" is already in pool

    def test_duplicate_links_deduped(self):
        results = [_cand("a", 0.9, links=["x", "x", "y", "x"])]
        ids, _ = collect_expansion_ids(results)
        assert ids == ["x", "y"]

    def test_max_links_per_seed_respected(self):
        results = [_cand("a", 0.9, links=["x", "y", "z"])]
        ids, _ = collect_expansion_ids(results, max_links_per_seed=2)
        assert ids == ["x", "y"]

    def test_max_expanded_respected_globally(self):
        results = [
            _cand("a", 0.9, links=["x", "y"]),
            _cand("b", 0.8, links=["z", "w"]),
        ]
        ids, _ = collect_expansion_ids(results, max_expanded=3)
        assert len(ids) == 3
        assert ids == ["x", "y", "z"]

    def test_malformed_links_ignored(self):
        results = [
            _cand("a", 0.9, links=[None, "", 42, "ok"]),
        ]
        ids, _ = collect_expansion_ids(results)
        assert ids == ["ok"]

    def test_non_list_links_field_ignored(self):
        results = [_cand("a", 0.9, links="oops-not-a-list")]
        ids, _ = collect_expansion_ids(results)
        assert ids == []


# ---------------------------------------------------------------------------
# build_expanded_candidates
# ---------------------------------------------------------------------------


class TestBuildExpandedCandidates:
    def test_builds_candidates_with_scaled_score(self):
        fetched = [_mem("x", data="expanded-data")]
        seed_scores = {"x": 0.8}
        out = build_expanded_candidates(fetched, seed_scores, expansion_score_weight=0.5)
        assert len(out) == 1
        assert out[0]["id"] == "x"
        assert out[0]["score"] == pytest.approx(0.4)
        assert out[0]["payload"]["data"] == "expanded-data"
        assert out[0]["_source"] == "graph_expansion"

    def test_score_is_clamped_to_unit_interval(self):
        fetched = [_mem("x", data="hi")]
        out = build_expanded_candidates(fetched, {"x": 2.0}, expansion_score_weight=1.0)
        assert out[0]["score"] == 1.0

    def test_memory_without_payload_data_is_dropped(self):
        m = SimpleNamespace(id="x", payload={})  # no "data"
        out = build_expanded_candidates([m], {"x": 0.9})
        assert out == []

    def test_memory_without_id_is_dropped(self):
        m = SimpleNamespace(id=None, payload={"data": "ok"})
        out = build_expanded_candidates([m], {})
        assert out == []

    def test_handles_none_items_gracefully(self):
        out = build_expanded_candidates([None, _mem("x")], {"x": 0.5})
        assert len(out) == 1 and out[0]["id"] == "x"


# ---------------------------------------------------------------------------
# expand_with_links (end-to-end with a fake fetcher)
# ---------------------------------------------------------------------------


class TestExpandWithLinks:
    def test_noop_when_no_expansions_found(self):
        results = [_cand("a", 0.9)]  # no links at all
        fetcher_calls: List[List[str]] = []

        def fetcher(ids):
            fetcher_calls.append(ids)
            return []

        out = expand_with_links(results, fetcher)
        assert out == results
        assert fetcher_calls == []  # fetcher must not be called

    def test_appends_expanded_and_resorts(self):
        """The expanded item should land BELOW the strong seed but ABOVE
        a weaker existing candidate."""
        results = [
            _cand("top", 0.95, links=["nbr"]),
            _cand("weak", 0.30),
        ]

        def fetcher(ids):
            assert ids == ["nbr"]
            return [_mem("nbr")]

        out = expand_with_links(results, fetcher, expansion_score_weight=0.85)
        ids_order = [c["id"] for c in out]
        # top (0.95) > nbr (0.95*0.85=0.8075) > weak (0.30)
        assert ids_order == ["top", "nbr", "weak"]
        # Original input must not be mutated.
        assert [c["id"] for c in results] == ["top", "weak"]

    def test_fetcher_exception_degrades_gracefully(self):
        results = [_cand("a", 0.9, links=["x"])]

        def fetcher(ids):
            raise RuntimeError("store boom")

        out = expand_with_links(results, fetcher)
        # Must return the original (as a fresh list), never raise.
        assert [c["id"] for c in out] == ["a"]

    def test_does_not_duplicate_if_fetched_already_in_pool(self):
        """Pathological fetcher that returns an id already present — dedup."""
        results = [_cand("a", 0.9, links=["x"]), _cand("x", 0.2)]

        def fetcher(ids):
            return [_mem("x")]

        out = expand_with_links(results, fetcher)
        assert sum(1 for c in out if c["id"] == "x") == 1


# ---------------------------------------------------------------------------
# make_vector_store_fetcher
# ---------------------------------------------------------------------------


class TestMakeVectorStoreFetcher:
    def test_prefers_get_batch_when_available(self):
        calls = {"batch": 0, "get": 0}

        class Store:
            def get_batch(self, ids):
                calls["batch"] += 1
                return [_mem(i) for i in ids]

            def get(self, vector_id):  # should not be called
                calls["get"] += 1
                return _mem(vector_id)

        fetcher = make_vector_store_fetcher(Store())
        out = fetcher(["a", "b"])
        assert [m.id for m in out] == ["a", "b"]
        assert calls == {"batch": 1, "get": 0}

    def test_falls_back_to_per_id_get(self):
        calls = {"get": 0}

        class Store:
            def get(self, vector_id):
                calls["get"] += 1
                return _mem(vector_id)

        fetcher = make_vector_store_fetcher(Store())
        out = fetcher(["a", "b"])
        assert [m.id for m in out] == ["a", "b"]
        assert calls["get"] == 2

    def test_per_id_get_failure_is_skipped_not_raised(self):
        class Store:
            def get(self, vector_id):
                if vector_id == "bad":
                    raise RuntimeError("nope")
                return _mem(vector_id)

        fetcher = make_vector_store_fetcher(Store())
        out = fetcher(["a", "bad", "b"])
        assert [m.id for m in out] == ["a", "b"]


# ---------------------------------------------------------------------------
# Back-compat: default config MUST NOT change search behaviour
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    def test_default_graph_expansion_config_disabled(self):
        from mem0.configs.base import GraphExpansionConfig, MemoryConfig

        cfg = MemoryConfig()
        assert isinstance(cfg.graph_expansion, GraphExpansionConfig)
        assert cfg.graph_expansion.enabled is False
