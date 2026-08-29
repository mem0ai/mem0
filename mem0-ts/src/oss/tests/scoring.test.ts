/// <reference types="jest" />

import {
  ENTITY_BOOST_WEIGHT,
  scoreAndRank,
  W_BM25,
  W_ENTITY,
  W_SEMANTIC,
} from "../src/utils/scoring";

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
    expect(details.weights).toEqual({
      semantic: W_SEMANTIC,
      bm25: W_BM25,
      entity: W_ENTITY,
    });
    expect(details.finalScore).toBeCloseTo(0.72);
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
    expect(W_SEMANTIC + W_BM25 + W_ENTITY).toBeCloseTo(1.0);
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
    expect(scored[0].score).toBeCloseTo((W_BM25 * 0.99) / (W_BM25 + W_ENTITY));
  });

  it("rescales entity boosts out of ENTITY_BOOST_WEIGHT", () => {
    const results = [{ id: "a", score: 0.8, payload: {} }];
    const scored = scoreAndRank(results, {}, { a: 0.3 }, 0.1, 10);
    expect(scored[0].score).toBeCloseTo(
      W_SEMANTIC * 0.8 + W_ENTITY * (0.3 / ENTITY_BOOST_WEIGHT),
    );
  });
});
