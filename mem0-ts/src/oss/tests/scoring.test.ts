/// <reference types="jest" />

import {
  ENTITY_BOOST_WEIGHT,
  RECENCY_HALF_LIFE_DAYS,
  scoreAndRank,
  W_BM25,
  W_ENTITY,
  W_RECENCY,
  W_SEMANTIC,
} from "../src/utils/scoring";

const aged = (id: string, days: number, score = 0.8) => ({
  id,
  score,
  payload: {
    created_at: new Date(Date.now() - days * 86_400_000).toISOString(),
  },
});

describe("scoreAndRank", () => {
  const results = [
    { id: "a", score: 0.8, payload: { data: "mem a" } },
    { id: "b", score: 0.5, payload: { data: "mem b" } },
  ];

  it("omits scoreDetails by default", () => {
    const scored = scoreAndRank(results, {}, {}, 0.1, 10);
    expect(scored[0].scoreDetails).toBeUndefined();
    expect(scored[1].scoreDetails).toBeUndefined();
  });

  it("omits scoreDetails when explain is false", () => {
    const scored = scoreAndRank(results, {}, {}, 0.1, 10, false);
    expect(scored[0].scoreDetails).toBeUndefined();
  });

  it("includes scoreDetails when explain is true", () => {
    const bm25 = { a: 0.6 };
    const entity = { a: 0.3 };
    const scored = scoreAndRank(results, bm25, entity, 0.1, 10, true);

    const details = scored[0].scoreDetails!;
    expect(details).toBeDefined();
    expect(details.semanticScore).toBe(0.8);
    expect(details.bm25Score).toBe(0.6);
    expect(details.entityBoost).toBe(0.3);
    expect(details.recencyScore).toBe(0); // no timestamp on this payload
    expect(details.weights).toEqual({
      semantic: W_SEMANTIC,
      bm25: W_BM25,
      entity: W_ENTITY,
      recency: W_RECENCY,
    });
    expect(details.finalScore).toBeCloseTo(
      W_SEMANTIC * 0.8 + W_BM25 * 0.6 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT),
    );
    expect(details.threshold).toBe(0.1);
  });

  it("includes scoreDetails for results without bm25/entity signals", () => {
    const scored = scoreAndRank(results, {}, {}, 0.1, 10, true);

    const details = scored[0].scoreDetails!;
    expect(details.semanticScore).toBe(0.8);
    expect(details.bm25Score).toBe(0);
    expect(details.entityBoost).toBe(0);
    expect(details.finalScore).toBeCloseTo(W_SEMANTIC * 0.8);
  });
});

describe("score comparability", () => {
  // Regression: the divisor was chosen from whether ANY candidate in the batch
  // had a BM25 or entity signal, so an unrelated memory matching keywords
  // silently rescaled everyone else's score.
  it("leaves a score unchanged when another candidate matches keywords", () => {
    const results = [
      { id: "a", score: 0.92, payload: {} },
      { id: "b", score: 0.41, payload: {} },
    ];

    const alone = scoreAndRank(results, {}, {}, 0.1, 10);
    const withBm25OnB = scoreAndRank(results, { b: 0.9 }, {}, 0.1, 10);

    const scoreOf = (scored: typeof alone, id: string) =>
      scored.find((s) => s.id === id)!.score;

    expect(scoreOf(alone, "a")).toBeCloseTo(scoreOf(withBm25OnB, "a"));
  });

  it("keeps the weights summing to one so scores stay in range", () => {
    expect(W_SEMANTIC + W_BM25 + W_ENTITY + W_RECENCY).toBeCloseTo(1.0);
  });
});

describe("recency", () => {
  // Regression: created_at was stored on every memory and never read, so a
  // preference stated two years ago outranked last week's correction whenever
  // it embedded fractionally better.
  it("prefers the newer memory when relevance ties", () => {
    const scored = scoreAndRank(
      [aged("old", 730), aged("new", 1)],
      {},
      {},
      0.1,
      10,
    );
    expect(scored.map((s) => s.id)).toEqual(["new", "old"]);
  });

  it("halves the recency signal at the half life", () => {
    const recencyOf = (s: ReturnType<typeof scoreAndRank>) =>
      s[0].score - W_SEMANTIC * 0.8;
    const fresh = scoreAndRank([aged("a", 0)], {}, {}, 0.1, 1);
    const old = scoreAndRank(
      [aged("a", RECENCY_HALF_LIFE_DAYS)],
      {},
      {},
      0.1,
      1,
    );
    expect(recencyOf(old)).toBeCloseTo(recencyOf(fresh) / 2, 3);
  });

  it("cannot outweigh relevance", () => {
    const scored = scoreAndRank(
      [
        { id: "relevant", score: 0.9, payload: {} },
        aged("fresh_but_vague", 0, 0.2),
      ],
      {},
      {},
      0.1,
      10,
    );
    expect(scored[0].id).toBe("relevant");
  });

  it("gives no credit for a missing or unparseable timestamp", () => {
    const missing = scoreAndRank(
      [{ id: "a", score: 0.8, payload: {} }],
      {},
      {},
      0.1,
      10,
    );
    const garbage = scoreAndRank(
      [{ id: "a", score: 0.8, payload: { created_at: "last tuesday" } }],
      {},
      {},
      0.1,
      10,
    );
    expect(missing[0].score).toBeCloseTo(W_SEMANTIC * 0.8);
    expect(garbage[0].score).toBeCloseTo(W_SEMANTIC * 0.8);
  });

  // Regression: OSS payloads store camelCase createdAt/updatedAt while the
  // REST and Python sides use snake_case, and both reach scoreAndRank. Reading
  // one spelling scored every memory from the other as maximally stale.
  it("reads camelCase and snake_case timestamps alike", () => {
    const fresh = new Date(Date.now() - 86_400_000).toISOString();
    const camel = scoreAndRank(
      [{ id: "a", score: 0.8, payload: { createdAt: fresh } }],
      {},
      {},
      0.1,
      1,
    );
    const snake = scoreAndRank(
      [{ id: "a", score: 0.8, payload: { created_at: fresh } }],
      {},
      {},
      0.1,
      1,
    );
    expect(camel[0].score).toBeCloseTo(snake[0].score);
    expect(camel[0].score).toBeGreaterThan(W_SEMANTIC * 0.8);
  });

  it("prefers updated_at over created_at", () => {
    const old = new Date(Date.now() - 730 * 86_400_000).toISOString();
    const recent = new Date(Date.now() - 86_400_000).toISOString();
    const scored = scoreAndRank(
      [
        {
          id: "a",
          score: 0.8,
          payload: { created_at: old, updated_at: recent },
        },
        { id: "b", score: 0.8, payload: { created_at: old } },
      ],
      {},
      {},
      0.1,
      10,
    );
    expect(scored.map((s) => s.id)).toEqual(["a", "b"]);
  });
});

describe("keyword-only candidates", () => {
  // A BM25 hit outside the semantic topK must still be rankable. The semantic
  // threshold describes a score we actually measured; a keyword-only candidate
  // never got one, so gating it on a placeholder 0.0 silently discarded every
  // exact-term match that embedded poorly.
  it("survives the semantic threshold", () => {
    const results = [
      { id: "a", score: 0.5, payload: { data: "mem a" } },
      { id: "b", score: 0.0, keywordOnly: true, payload: { data: "mem b" } },
    ];
    const scored = scoreAndRank(results, { b: 0.9 }, {}, 0.1, 10);
    expect(scored.map((s) => s.id)).toContain("b");
  });

  it("is gated on its own bm25 score", () => {
    const results = [
      { id: "b", score: 0.0, keywordOnly: true, payload: { data: "mem b" } },
    ];
    const scored = scoreAndRank(results, { b: 0.05 }, {}, 0.1, 10);
    expect(scored).toEqual([]);
  });

  it("is not penalized for the semantic signal it could never earn", () => {
    const results = [
      { id: "a", score: 0.5, payload: {} },
      { id: "b", score: 0.0, keywordOnly: true, payload: {} },
    ];
    const scored = scoreAndRank(results, { b: 0.99 }, {}, 0.1, 10);

    expect(scored.map((s) => s.id)).toEqual(["b", "a"]);
    expect(scored[0].score).toBeCloseTo(
      (W_BM25 * 0.99) / (W_BM25 + W_ENTITY + W_RECENCY),
    );
  });

  it("rescales entity boosts out of ENTITY_BOOST_WEIGHT", () => {
    const results = [{ id: "a", score: 0.8, payload: {} }];
    const scored = scoreAndRank(results, {}, { a: 0.3 }, 0.1, 10);
    expect(scored[0].score).toBeCloseTo(
      W_SEMANTIC * 0.8 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT),
    );
  });
});
