"""Regression tests for the opt-in recency term in score_and_rank (issue #7535).

Design contract locked in the issue discussion (zhaoyiDing-321q's comment):

- Harmonic decay anchored at query time: recency = 1 / (1 + age_days / tau).
  Query-time anchoring makes each candidate's recency independent of the rest
  of the candidate set (PR #7538's min-max normalization was not, which is why
  it could flip a pair's order when an unrelated candidate joined).
- Effective time per memory: updated_at, falling back to created_at.
- Multiplicative freshness discount: combined = base * (1 - w * (1 - recency))
  with base = (semantic + bm25 + entity) / max_possible. A memory always keeps
  at least base * (1 - w) of its score; being fresh lifts a weak match only in
  proportion to its own base (relevance gates the recency effect), and the
  ordering is scale-free.
- Defaults: recency_weight=0.0 (opt-in), tau=365 days (recency = 0.5 at age 1y);
  suggested activation weight is 0.25 -- 0.1 provably cannot flip the issue's
  "team" pair (the flip needs w ~= 0.22 under the discount form).
- 'now' is injectable so tests are deterministic.

All expected scores below are hand-computed constants (age in whole days
against NOW), not re-evaluations of the implementation formula.
"""

import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.utils.scoring import score_and_rank

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
W = 0.25  # suggested activation weight from the issue comment
TAU = 365.0


def _cand(mem_id, score, created=None, updated=None):
    payload = {"data": mem_id}
    if created is not None:
        payload["created_at"] = created
    if updated is not None:
        payload["updated_at"] = updated
    return {"id": mem_id, "score": score, "payload": payload}


def _rank(cands, weight=W, tau=TAU, now=NOW, **kwargs):
    return score_and_rank(
        cands,
        kwargs.pop("bm25_scores", {}),
        kwargs.pop("entity_boosts", {}),
        threshold=kwargs.pop("threshold", 0.1),
        top_k=kwargs.pop("top_k", 100),
        recency_weight=weight,
        recency_tau_days=tau,
        now=now,
        **kwargs,
    )


class TestIssue7535Regression:
    """The three fact pairs from the issue repro (repro_7535.py / before.txt).

    Semantic scores are the observed production values; dates are the values
    the repro injected via metadata created_at. Expected combined scores use
    age in whole days, e.g. Chicago old: 1408d -> r = 1/(1+1408/365) = 0.205867.
    """

    def test_chicago_pair_flips_with_w025(self):
        cands = [
            _cand("old", 0.307339, created="2023-01-10T00:00:00Z"),
            _cand("new", 0.307282, created="2023-09-02T00:00:00Z"),
        ]
        ranked = _rank(cands)
        assert [c["id"] for c in ranked] == ["new", "old"]
        # old: 0.307339 * (1 - 0.25*(1-0.205866)) = 0.246322
        assert ranked[1]["score"] == pytest.approx(0.246322, abs=1e-5)
        # new (age 1173d -> r = 0.237321): 0.307282 * (1 - 0.25*(1-0.237321)) = 0.248693
        assert ranked[0]["score"] == pytest.approx(0.248693, abs=1e-5)

    def test_team_pair_flips_with_w025(self):
        cands = [
            _cand("old", 0.650019, created="2023-01-18T00:00:00Z"),
            _cand("new", 0.646028, created="2023-07-20T00:00:00Z"),
        ]
        ranked = _rank(cands)
        assert [c["id"] for c in ranked] == ["new", "old"]
        # old (age 1400d -> r = 0.206799): 0.521120
        assert ranked[1]["score"] == pytest.approx(0.521120, abs=1e-5)
        # new (age 1217d -> r = 0.230721): 0.521784
        assert ranked[0]["score"] == pytest.approx(0.521784, abs=1e-5)

    def test_therapy_pair_keeps_new_first(self):
        # New memory already leads semantically (0.540209 vs 0.449505); recency
        # must only reinforce, never invert, a pair the semantic pass got right.
        cands = [
            _cand("old", 0.449505, created="2023-04-03T00:00:00Z"),
            _cand("new", 0.540209, created="2023-11-03T00:00:00Z"),
        ]
        ranked = _rank(cands)
        assert [c["id"] for c in ranked] == ["new", "old"]
        # old (age 1325d -> r = 0.215976): 0.361399
        assert ranked[1]["score"] == pytest.approx(0.361399, abs=1e-5)
        # new (age 1111d -> r = 0.247290): 0.438554
        assert ranked[0]["score"] == pytest.approx(0.438554, abs=1e-5)

    def test_default_weight_zero_keeps_current_order(self):
        # Opt-in guard: with the default weight the observed (broken) ordering
        # is reproduced bit-for-bit, so default installs see zero behavior change.
        cands = [
            _cand("old", 0.307339, created="2023-01-10T00:00:00Z"),
            _cand("new", 0.307282, created="2023-09-02T00:00:00Z"),
        ]
        ranked = _rank(cands, weight=0.0)
        assert [c["id"] for c in ranked] == ["old", "new"]
        assert ranked[0]["score"] == pytest.approx(0.307339, abs=1e-6)

    def test_weight_01_cannot_flip_team_pair(self):
        # Negative control, the reason 0.25 is the suggested value: at w=0.1 the
        # newer side keeps only 0.9231 vs old's 0.9207 of base (+0.26%), below
        # the 0.61% base gap; the flip needs w ~= 0.22.
        cands = [
            _cand("old", 0.650019, created="2023-01-18T00:00:00Z"),
            _cand("new", 0.646028, created="2023-07-20T00:00:00Z"),
        ]
        ranked = _rank(cands, weight=0.1)
        assert ranked[0]["id"] == "old"
        # old: 0.598459; new: 0.596330
        assert ranked[0]["score"] == pytest.approx(0.598459, abs=1e-5)
        assert ranked[1]["score"] == pytest.approx(0.596330, abs=1e-5)


class TestCandidateSetInvariance:
    """Query-time anchoring must make ranking independent of the candidate set.

    The scenario below is the arch-flip counterexample that breaks PR #7538's
    min-max normalization: under min-max the pair ranks old < new alone, but
    old > new once 'arch' (low score, much older) enters the survivor set.
    """

    OLD = _cand("old", 0.650003, created="2026-08-01T00:00:00Z")
    NEW = _cand("new", 0.646012, created="2026-09-01T00:00:00Z")
    ARCH = _cand("arch", 0.310000, created="2020-01-01T00:00:00Z")

    def test_arch_flip_case_does_not_flip(self):
        pair = _rank([self.OLD, self.NEW])
        trio = _rank([self.OLD, self.NEW, self.ARCH])

        assert [c["id"] for c in pair] == ["new", "old"]
        assert [c["id"] for c in trio] == ["new", "old", "arch"]
        # Scores must be identical with and without the third candidate:
        # old (age 109d -> r = 0.770042): 0.612635
        # new (age 78d  -> r = 0.823928): 0.617576
        # arch (age 2513d -> r = 0.126824): 0.242329
        for ranked in (pair, trio):
            by_id = {c["id"]: c["score"] for c in ranked}
            assert by_id["old"] == pytest.approx(0.612635, abs=1e-5)
            assert by_id["new"] == pytest.approx(0.617576, abs=1e-5)
        assert trio[2]["score"] == pytest.approx(0.242329, abs=1e-5)

    def test_pairwise_order_invariant_under_insertions(self):
        # Seeded, deterministic: delete any third candidate from a random pool
        # and every remaining pair must keep its relative order. Candidates
        # whose final scores tie are skipped -- a tie has no order to preserve.
        rng = random.Random(20261118)
        base = datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp()
        end = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()
        pool = [
            _cand(
                f"m{i}",
                round(0.3 + 0.65 * rng.random(), 6),
                created=datetime.fromtimestamp(base + (end - base) * rng.random(), tz=timezone.utc).isoformat(),
            )
            for i in range(30)
        ]
        full = _rank(pool)
        full_score = {c["id"]: c["score"] for c in full}
        for c in full:
            assert c["score"] == c["score"]  # no NaN

        ids = list(full_score)
        for drop_id in ids[::3]:  # remove every third candidate, one at a time
            reduced = _rank([c for c in pool if c["id"] != drop_id])
            red_score = {c["id"]: c["score"] for c in reduced}
            assert red_score == {k: v for k, v in full_score.items() if k != drop_id}
            for i, a in enumerate(ids):
                if a == drop_id:
                    continue
                for b in ids[i + 1 :]:
                    if b == drop_id or full_score[a] == full_score[b]:
                        continue  # tie: both orders are valid
                    expected = full_score[a] > full_score[b]
                    assert (red_score[a] > red_score[b]) == expected


class TestRecencyEdgeCases:
    def test_created_today_scores_recency_one(self):
        ranked = _rank([_cand("a", 0.5, created="2026-11-18T00:00:00Z")])
        # r = 1 -> discount 1 -> final = base = 0.5
        assert ranked[0]["score"] == pytest.approx(0.5, abs=1e-6)

    def test_missing_timestamp_scores_recency_zero(self):
        ranked = _rank([_cand("a", 0.5)])
        # r = 0 -> discount 0.75 -> 0.5 * 0.75 = 0.375, no crash
        assert ranked[0]["score"] == pytest.approx(0.375, abs=1e-6)

    def test_unparseable_timestamp_scores_recency_zero(self):
        ranked = _rank([_cand("a", 0.5, created="not-a-date")])
        assert ranked[0]["score"] == pytest.approx(0.375, abs=1e-6)

    def test_future_timestamp_clamps_to_recency_one(self):
        ranked = _rank([_cand("a", 0.5, created="2099-01-01T00:00:00Z")])
        # age clamps to 0 -> r = 1 -> no discount
        assert ranked[0]["score"] == pytest.approx(0.5, abs=1e-6)

    def test_updated_at_preferred_over_created_at(self):
        # created_at is ancient; a recent update must set the effective time.
        ranked = _rank([_cand("a", 0.5, created="2020-01-01T00:00:00Z", updated="2026-11-01T00:00:00Z")])
        # age 17d -> r = 0.955498; discount 0.988874 -> 0.494437
        assert ranked[0]["score"] == pytest.approx(0.494437, abs=1e-5)

    def test_extreme_age_span_does_not_collapse_scores(self):
        # Min-max failure mode being guarded against: with a huge span the old
        # candidate's relative position must still follow its absolute age.
        cands = [
            _cand("ancient", 0.5, created="2007-11-19T00:00:00Z"),  # 6939d ago
            _cand("old", 0.5, created="2015-08-10T00:00:00Z"),  # 4118d ago
            _cand("recent", 0.5, created="2026-11-17T00:00:00Z"),  # 1d ago
        ]
        ranked = _rank(cands)
        assert [c["id"] for c in ranked] == ["recent", "old", "ancient"]
        # old: r = 0.081419 -> discount 0.770355 -> 0.385177
        # ancient: r = 0.049973 -> discount 0.762493 -> 0.381247
        # Distinct, non-zero, strictly ordered -- not flattened.
        assert ranked[1]["score"] == pytest.approx(0.385177, abs=1e-5)
        assert ranked[2]["score"] == pytest.approx(0.381247, abs=1e-5)
        assert ranked[2]["score"] > 0.375  # 0.375 == max-discount floor

    def test_threshold_gates_semantic_before_recency(self):
        # A brand-new memory below the semantic threshold must stay excluded:
        # recency rescues ranking between survivors, it cannot revive the gated.
        cands = [
            _cand("low_but_new", 0.05, created="2026-11-18T00:00:00Z"),
            _cand("ok", 0.5, created="2020-01-01T00:00:00Z"),
        ]
        ranked = _rank(cands, threshold=0.1)
        assert [c["id"] for c in ranked] == ["ok"]

    def test_smaller_tau_sharpens_recent_gradient(self):
        # tau controls how fast recency decays: 1d-vs-30d separation must be
        # larger at tau=90 than at tau=730. Asserted via ranking a tie.
        cands = [
            _cand("day1", 0.5, created="2026-11-17T00:00:00Z"),
            _cand("day30", 0.5, created="2026-10-19T00:00:00Z"),
        ]
        sharp = _rank(cands, tau=90.0)
        flat = _rank(cands, tau=730.0)
        assert (sharp[0]["score"] - sharp[1]["score"]) > (flat[0]["score"] - flat[1]["score"])
        # tau=90: r1=0.989011 -> 0.498626; r30=0.750000 -> 0.468750
        assert [c["id"] for c in sharp] == ["day1", "day30"]
        assert sharp[0]["score"] == pytest.approx(0.498626, abs=1e-5)
        assert sharp[1]["score"] == pytest.approx(0.468750, abs=1e-5)

    def test_recency_composes_with_bm25_and_entity_divisor(self):
        # base = (0.8 + 0.6 + 0.3) / 2.5 = 0.68; today -> recency 1 -> no
        # discount (max_possible no longer grows with the recency weight).
        cands = [_cand("a", 0.8, created="2026-11-18T00:00:00Z")]
        ranked = _rank(cands, bm25_scores={"a": 0.6}, entity_boosts={"a": 0.3})
        assert ranked[0]["score"] == pytest.approx(0.68, abs=1e-5)

    def test_explain_includes_recency_when_active(self):
        ranked = _rank([_cand("a", 0.8, created="2026-11-18T00:00:00Z")], explain=True)
        details = ranked[0]["score_details"]
        assert details["recency_score"] == pytest.approx(1.0, abs=1e-6)
        assert details["recency_weight"] == W

    def test_explain_omits_recency_when_weight_zero(self):
        ranked = _rank([_cand("a", 0.8, created="2026-11-18T00:00:00Z")], weight=0.0, explain=True)
        assert "recency_score" not in ranked[0]["score_details"]


def _build_parity_memory(mocker, memory_cls):
    """Memory/AsyncMemory with provider SDKs mocked out and recency enabled.

    The embedder, vector store, LLM, and history DB are swapped for mocks (the
    provider boundary); lemmatization, scoring, and the sync/async wiring under
    test run for real. BM25 and entity signals are neutralized so the fixture
    isolates the semantic + recency path.
    """
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)
    mocker.patch("mem0.utils.factory.VectorStoreFactory.create", mocker.MagicMock())
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.MEM0_TELEMETRY", False)

    memory = memory_cls()
    memory.config = mocker.MagicMock()
    memory.config.recency_weight = W
    memory.config.recency_tau_days = TAU
    memory.vector_store = mocker.MagicMock()
    return memory


# With semantic only, old outranks new; enabled recency must flip the pair in
# BOTH implementations. Dates differ so the harmonic term separates them.
PAIR_FIXTURE = [
    SimpleNamespace(
        id="old",
        score=0.650003,
        payload={"data": "old", "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z"},
    ),
    SimpleNamespace(
        id="new",
        score=0.646012,
        payload={"data": "new", "created_at": "2026-09-01T00:00:00Z", "updated_at": "2026-09-01T00:00:00Z"},
    ),
]


class TestSyncAsyncParity:
    """One shared score_and_rank feeds both _search_vector_store paths
    (mem0/memory/main.py sync Step 8 and async Step 8). Drive both over the
    same fixture store and require the same outcome: paraphrase-level inputs
    must yield the same ranking and scores."""

    def _wire(self, memory):
        memory.vector_store.search.return_value = PAIR_FIXTURE
        memory.vector_store.keyword_search.return_value = None

    def test_sync_flips_pair(self, mocker):
        mocker.patch("mem0.memory.main.extract_entities", return_value=[])
        memory = _build_parity_memory(mocker, Memory)
        self._wire(memory)
        ranked = memory._search_vector_store("q", filters={"user_id": "u"}, limit=10)
        assert [r["id"] for r in ranked] == ["new", "old"]

    @pytest.mark.asyncio
    async def test_async_search_matches_sync_ranking(self, mocker):
        mocker.patch("mem0.memory.main.extract_entities", return_value=[])
        sync_m = _build_parity_memory(mocker, Memory)
        async_m = _build_parity_memory(mocker, AsyncMemory)
        self._wire(sync_m)
        self._wire(async_m)

        sync_ranked = sync_m._search_vector_store("q", filters={"user_id": "u"}, limit=10)
        async_ranked = await async_m._search_vector_store("q", filters={"user_id": "u"}, limit=10)

        assert [r["id"] for r in async_ranked] == ["new", "old"]
        # Identical order; scores equal up to the sub-second delta between the
        # two `now` samples (harmonic age is fractional-day).
        assert [r["id"] for r in async_ranked] == [r["id"] for r in sync_ranked]
        for s, a in zip(sync_ranked, async_ranked):
            assert a["score"] == pytest.approx(s["score"], rel=1e-6)
