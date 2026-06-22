/// <reference types="jest" />

import { scoreAndRank } from "../src/utils/scoring";

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
    expect(details.rawScore).toBeCloseTo(1.7);
    expect(details.maxPossibleScore).toBe(2.5);
    expect(details.finalScore).toBeCloseTo(0.68);
    expect(details.threshold).toBe(0.1);
  });

  it("includes scoreDetails for results without bm25/entity signals", () => {
    const scored = scoreAndRank(results, {}, {}, 0.1, 10, true);

    const details = scored[0].scoreDetails!;
    expect(details.semanticScore).toBe(0.8);
    expect(details.bm25Score).toBe(0);
    expect(details.entityBoost).toBe(0);
    expect(details.rawScore).toBe(0.8);
    expect(details.maxPossibleScore).toBe(1.0);
    expect(details.finalScore).toBe(0.8);
  });

  it("allows BM25 to rescue candidates below semantic threshold", () => {
    const lowSemantic = [{ id: "a", score: 0.05, payload: { data: "mem a" } }];
    const scored = scoreAndRank(lowSemantic, { a: 0.95 }, {}, 0.1, 10);
    expect(scored).toHaveLength(1);
    expect(scored[0].id).toBe("a");
  });
});
