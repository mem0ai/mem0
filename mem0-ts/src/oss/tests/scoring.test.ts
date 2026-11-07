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

  describe("reciprocal rank fusion", () => {
    const candidates = [
      { id: "a", score: 0.95, payload: { data: "a" } },
      { id: "b", score: 0.8, payload: { data: "b" } },
      { id: "c", score: 0.7, payload: { data: "c" } },
    ];

    it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
      "excludes nonfinite semantic score %p before ranking",
      (invalidScore) => {
        const scored = scoreAndRank(
          [
            { id: "invalid", score: invalidScore, payload: {} },
            { id: "valid", score: 0.8, payload: {} },
          ],
          { invalid: 1.0 },
          {},
          0.1,
          10,
          true,
          "rrf",
        );
        expect(scored.map((item) => item.id)).toEqual(["valid"]);
        expect(scored[0].score).toBeCloseTo(1 / 61);
        expect(scored[0].scoreDetails!.semanticRank).toBe(1);
      },
    );

    it("fuses all three channels directly and can reverse additive ordering", () => {
      const additive = scoreAndRank(
        candidates,
        { a: 0.1, b: 0.9, c: 0.8 },
        { a: 0.1, b: 0.2, c: 0.95 },
        0.1,
        3,
      );
      const scored = scoreAndRank(
        candidates,
        { a: 0.1, b: 0.9, c: 0.8 },
        { a: 0.1, b: 0.2, c: 0.95 },
        0.1,
        3,
        true,
        "rrf",
        1,
      );

      // Additive scoring favors c here because its raw auxiliary scores are
      // largest, while direct RRF favors b's consistently strong ranks.
      expect(additive[0].id).toBe("c");
      expect(scored.map((result) => result.id)).toEqual(["b", "c", "a"]);
      const details = scored[0].scoreDetails!;
      expect(details.fusionStrategy).toBe("rrf");
      expect(details.rrfK).toBe(1);
      expect(details.semanticRank).toBe(2);
      expect(details.bm25Rank).toBe(1);
      expect(details.entityRank).toBe(2);
      expect(details.rawScore).toBeCloseTo(1 / 3 + 1 / 2 + 1 / 3);
      expect(details.finalScore).toBe(details.rawScore);
      expect(details.maxPossibleScore).toBe(3 / 2);
    });

    it("is invariant to positive score scaling within each auxiliary channel", () => {
      const original = scoreAndRank(
        candidates,
        { a: 0.1, b: 0.9, c: 0.8 },
        { a: 0.1, b: 0.2, c: 0.95 },
        0.1,
        3,
        true,
        "rrf",
        60,
      );
      const scaled = scoreAndRank(
        candidates,
        { a: 10, b: 90, c: 80 },
        { a: 10, b: 20, c: 95 },
        0.1,
        3,
        true,
        "rrf",
        60,
      );

      expect(scaled.map((result) => result.id)).toEqual(
        original.map((result) => result.id),
      );
      expect(scaled.map((result) => result.score)).toEqual(
        original.map((result) => result.score),
      );
    });

    it("uses average ranks for ties without changing ranks when input order changes", () => {
      const forward = scoreAndRank(
        candidates,
        { a: 1, b: 1, c: 0.5 },
        { a: 0.8, b: 0.8, c: 0.1 },
        0.1,
        3,
        true,
        "rrf",
        10,
      );
      const reverse = scoreAndRank(
        [...candidates].reverse(),
        { a: 1, b: 1, c: 0.5 },
        { a: 0.8, b: 0.8, c: 0.1 },
        0.1,
        3,
        true,
        "rrf",
        10,
      );

      const detailsById = (results: typeof forward) =>
        new Map(results.map((result) => [result.id, result.scoreDetails!]));
      const forwardDetails = detailsById(forward);
      const reverseDetails = detailsById(reverse);
      expect(forwardDetails.get("a")?.semanticRank).toBe(
        reverseDetails.get("a")?.semanticRank,
      );
      expect(forwardDetails.get("a")?.bm25Rank).toBe(1.5);
      expect(forwardDetails.get("b")?.bm25Rank).toBe(1.5);
      expect(forwardDetails.get("a")?.entityRank).toBe(1.5);
      expect(forwardDetails.get("b")?.entityRank).toBe(1.5);
      expect(forwardDetails.get("a")?.finalScore).toBe(
        reverseDetails.get("a")?.finalScore,
      );
    });

    it("ignores missing, zero, non-finite, noneligible, and auxiliary-only IDs", () => {
      const scored = scoreAndRank(
        [
          ...candidates,
          { id: "below-threshold", score: 0.05, payload: { data: "x" } },
        ],
        {
          a: 0,
          b: 1,
          "below-threshold": 100,
          extra: 100,
          invalid: Number.NaN,
        },
        { a: Number.POSITIVE_INFINITY, extra: 1 },
        0.1,
        10,
        true,
        "rrf",
        10,
      );

      expect(scored.map((result) => result.id)).toEqual([
        "b",
        "a",
        "below-threshold",
        "c",
      ]);
      expect(scored).not.toEqual(
        expect.arrayContaining([expect.objectContaining({ id: "extra" })]),
      );
      const belowDetails = scored.find(
        (result) => result.id === "below-threshold",
      )!.scoreDetails!;
      expect(belowDetails.semanticRank).toBe(4);
      expect(belowDetails.semanticContribution).toBe(0);
      const aDetails = scored.find(
        (result) => result.id === "a",
      )!.scoreDetails!;
      expect(aDetails.bm25Rank).toBeNull();
      expect(aDetails.entityRank).toBeNull();
      expect(aDetails.bm25Contribution).toBe(0);
      expect(aDetails.entityContribution).toBe(0);
      expect(aDetails.maxPossibleScore).toBe(3 / 11);
    });

    it("applies topK after fusing all eligible candidates", () => {
      const scored = scoreAndRank(
        candidates,
        { a: 0.1, b: 1, c: 0.9 },
        { a: 0.1, b: 1, c: 0.9 },
        0.1,
        1,
        false,
        "rrf",
        1,
      );

      expect(scored).toHaveLength(1);
      expect(scored[0].id).toBe("b");
    });

    it("admits keyword-only and entity-only candidates with supplied payloads", () => {
      const scored = (scoreAndRank as any)(
        [
          { id: "semantic", score: 0.95, payload: { data: "semantic" } },
          { id: "below-threshold", score: 0.05, payload: { data: "below" } },
        ],
        { "keyword-only": 100 },
        { "entity-only": 0.9 },
        0.1,
        10,
        true,
        "rrf",
        1,
        [
          { id: "keyword-only", payload: { data: "keyword" } },
          { id: "entity-only", payload: { data: "entity" } },
        ],
      );

      expect(scored.map((result: { id: string }) => result.id)).toEqual(
        expect.arrayContaining(["semantic", "keyword-only", "entity-only"]),
      );
      expect(scored).not.toEqual(
        expect.arrayContaining([
          expect.objectContaining({ id: "below-threshold" }),
        ]),
      );
    });

    it("keeps full source ranks while gating only the semantic vote", () => {
      const scored = (scoreAndRank as any)(
        [
          { id: "outside", score: 0.9, payload: { data: "outside" } },
          { id: "keyword-only", score: 0.05, payload: { data: "keyword" } },
        ],
        { "keyword-only": 10, outside: 1 },
        {},
        0.1,
        10,
        true,
        "rrf",
        1,
        [{ id: "keyword-only", payload: { data: "keyword" } }],
      );

      const details = scored.find(
        (result: any) => result.id === "keyword-only",
      ).scoreDetails;
      expect(details.semanticRank).toBe(2);
      expect(details.semanticContribution).toBe(0);
      expect(details.bm25Rank).toBe(1);
    });

    it("orders below-threshold semantic candidates before equal auxiliary-only ties", () => {
      const scored = scoreAndRank(
        [{ id: "below", score: 0.05, payload: { data: "below" } }],
        { keyword: 1 },
        { below: 1 },
        0.1,
        10,
        true,
        "rrf",
        1,
        [{ id: "keyword", payload: { data: "keyword" } }],
      );

      expect(scored.map((result) => result.id)).toEqual(["below", "keyword"]);
      expect(scored[0].score).toBe(scored[1].score);
      expect(scored[0].scoreDetails?.semanticScore).toBe(0.05);
      expect(scored[1].scoreDetails?.semanticScore).toBeNull();
      expect(scored[1].scoreDetails?.semanticContribution).toBe(0);
    });

    it("does not synthesize a semantic vote for null or undefined scores", () => {
      const scored = scoreAndRank(
        [
          { id: "null-score", score: null as any, payload: { data: "null" } },
          {
            id: "missing-score",
            score: undefined as any,
            payload: { data: "missing" },
          },
        ],
        { "keyword-only": 1 },
        {},
        0,
        10,
        true,
        "rrf",
        1,
        [{ id: "keyword-only", payload: { data: "keyword" } }],
      );

      expect(scored.map((result) => result.id)).toEqual(["keyword-only"]);
      expect(scored[0].scoreDetails?.semanticScore).toBeNull();
      expect(scored[0].scoreDetails?.semanticRank).toBeNull();
      expect(scored[0].scoreDetails?.semanticContribution).toBe(0);
    });

    it("preserves source tie order when an auxiliary payload fills a missing semantic score", () => {
      const rows = scoreAndRank(
        [
          { id: "first", score: Number.NaN },
          { id: "second", score: 0.05, payload: { data: "second" } },
        ],
        { second: 1, first: 1 },
        {},
        0.4,
        2,
        true,
        "rrf",
        60,
        [{ id: "first", payload: { data: "first" } }],
      );
      expect(rows.map((row) => row.id)).toEqual(["first", "second"]);
      expect(rows[0].scoreDetails?.semanticRank).toBeNull();
      expect(rows[0].score).toBe(rows[1].score);
    });

    it("keeps additive scoring and its explanation shape unchanged by default", () => {
      const scored = scoreAndRank(candidates, {}, {}, 0.1, 3, true);
      expect(scored[0].scoreDetails).not.toHaveProperty("fusionStrategy");
      expect(scored[0].scoreDetails).not.toHaveProperty("rrfK");
      expect(scored[0].score).toBeCloseTo(0.95);
    });

    it.each([
      ["unknown strategy", "weighted"],
      ["boolean strategy", true],
    ])("rejects %s", (_label: string, strategy: unknown) => {
      expect(() =>
        scoreAndRank(candidates, {}, {}, 0.1, 3, false, strategy as any),
      ).toThrow(/fusionStrategy/);
    });

    it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, false])(
      "rejects invalid rrfK %p",
      (rrfK: number | boolean) => {
        expect(() =>
          scoreAndRank(candidates, {}, {}, 0.1, 3, false, "rrf", rrfK as any),
        ).toThrow(/rrfK/);
      },
    );
  });
});
