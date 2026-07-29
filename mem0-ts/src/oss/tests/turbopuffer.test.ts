/// <reference types="jest" />

import { TurbopufferDB } from "../src/vector_stores/turbopuffer";

describe("TurbopufferDB score normalization", () => {
  it("normalizes euclidean_squared distances to a positive similarity", () => {
    const store = new TurbopufferDB({
      apiKey: "test-key",
      collectionName: "memories",
      distanceMetric: "euclidean_squared",
    });

    const results = (store as any).parseRows([
      { id: "near", $dist: 0.5, user_id: "u1" },
      { id: "far", $dist: 3, user_id: "u1" },
    ]);

    expect(results).toEqual([
      { id: "near", payload: { user_id: "u1" }, score: 2 / 3 },
      { id: "far", payload: { user_id: "u1" }, score: 1 / 4 },
    ]);
    expect(results[0].score).toBeGreaterThan(results[1].score);
    expect(results[1].score).toBeGreaterThan(0);
  });

  it("preserves cosine distance scoring", () => {
    const store = new TurbopufferDB({
      apiKey: "test-key",
      collectionName: "memories",
      distanceMetric: "cosine_distance",
    });

    const [result] = (store as any).parseRows([
      { id: "doc-1", $dist: 0.25, topic: "alpha" },
    ]);

    expect(result).toEqual({
      id: "doc-1",
      payload: { topic: "alpha" },
      score: 0.75,
    });
  });

  it("leaves missing distances undefined", () => {
    const store = new TurbopufferDB({
      apiKey: "test-key",
      collectionName: "memories",
      distanceMetric: "euclidean_squared",
    });

    const [result] = (store as any).parseRows([
      { id: "doc-1", topic: "alpha" },
    ]);

    expect(result).toEqual({
      id: "doc-1",
      payload: { topic: "alpha" },
      score: undefined,
    });
  });
});
