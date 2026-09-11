/// <reference types="jest" />
/**
 * Turbopuffer vector store — score conversion unit tests.
 *
 * Drives parseRows() through the public search() API with a virtually-mocked
 * @turbopuffer/turbopuffer peer, asserting the score returned per metric.
 */

const mockQuery = jest.fn();

jest.mock(
  "@turbopuffer/turbopuffer",
  () => ({
    __esModule: true,
    default: class {
      namespace() {
        return { query: mockQuery };
      }
    },
  }),
  { virtual: true },
);

import { TurbopufferDB } from "../src/vector_stores/turbopuffer";

function makeStore(distanceMetric?: string) {
  return new TurbopufferDB({
    apiKey: "test-key",
    collectionName: "mem0",
    ...(distanceMetric ? { distanceMetric } : {}),
  } as any);
}

async function scoreFor(
  distanceMetric: string | undefined,
  row: Record<string, any>,
): Promise<number | undefined> {
  mockQuery.mockResolvedValueOnce({ rows: [row] });
  const results = await makeStore(distanceMetric).search([0.1, 0.2, 0.3], 5);
  return results[0].score;
}

describe("TurbopufferDB score conversion", () => {
  it("keeps cosine distance as 1 - dist (default metric)", async () => {
    // cosine_distance is the default; a distance of 0.25 -> similarity 0.75.
    expect(await scoreFor(undefined, { id: "a", $dist: 0.25 })).toBeCloseTo(
      0.75,
      10,
    );
  });

  it("bounds an unbounded euclidean_squared distance to a 0..1 similarity", async () => {
    // $dist = 4.0 is a squared distance. 1 - 4.0 = -3.0 would invert ranking;
    // 1 / (1 + 4.0) = 0.2 keeps it higher-is-better and in range.
    const score = await scoreFor("euclidean_squared", { id: "a", $dist: 4.0 });
    expect(score).toBeCloseTo(0.2, 10);
    expect(score!).toBeGreaterThanOrEqual(0);
    expect(score!).toBeLessThanOrEqual(1);
  });

  it("ranks a nearer euclidean_squared hit above a farther one", async () => {
    mockQuery.mockResolvedValueOnce({
      rows: [
        { id: "near", $dist: 1.0 },
        { id: "far", $dist: 9.0 },
      ],
    });
    const results = await makeStore("euclidean_squared").search(
      [0.1, 0.2, 0.3],
      5,
    );
    const near = results.find((r) => r.id === "near")!;
    const far = results.find((r) => r.id === "far")!;
    expect(near.score!).toBeGreaterThan(far.score!);
  });

  it("preserves an undefined score when the row has no distance", async () => {
    expect(await scoreFor("euclidean_squared", { id: "a" })).toBeUndefined();
  });
});
