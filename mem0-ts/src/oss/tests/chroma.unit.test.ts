const mockCollection = {
  add: jest.fn(),
  get: jest.fn(),
  query: jest.fn(),
  update: jest.fn(),
  delete: jest.fn(),
};

jest.mock("chromadb", () => ({
  ChromaClient: jest.fn().mockImplementation(() => ({
    getOrCreateCollection: jest.fn().mockResolvedValue(mockCollection),
    getCollection: jest.fn().mockResolvedValue(mockCollection),
    listCollections: jest.fn().mockResolvedValue([]),
    deleteCollection: jest.fn().mockResolvedValue(undefined),
  })),
  CloudClient: jest.fn(),
}));

import { ChromaDB } from "../src/vector_stores/chroma";
import { bm25Score, tokenizeBm25 } from "../src/utils/bm25";

// generateWhereClause is a private static; reach it directly for unit testing.
const whereClause = (filters: any) =>
  (ChromaDB as any).generateWhereClause(filters);

describe("bm25Score", () => {
  const candidates = [
    { id: "a", payload: {}, tokens: tokenizeBm25("python memori layer agent") },
    { id: "b", payload: {}, tokens: tokenizeBm25("weather forecast today") },
    { id: "c", payload: {}, tokens: tokenizeBm25("python agent memori") },
  ];

  test("returns empty for no candidates or empty query", () => {
    expect(bm25Score([], ["python"], 5)).toEqual([]);
    expect(bm25Score(candidates, [], 5)).toEqual([]);
  });

  test("ranks documents containing the query terms first", () => {
    const results = bm25Score(candidates, tokenizeBm25("python memori"), 5);
    const ids = results.map((r) => r.id);
    expect(ids).toContain("a");
    expect(ids).toContain("c");
    // "weather" doc shares no terms -> filtered out.
    expect(ids).not.toContain("b");
  });

  test("scores are positive and sorted descending", () => {
    const results = bm25Score(candidates, tokenizeBm25("python"), 5);
    for (const r of results) {
      expect(r.score).toBeGreaterThan(0);
    }
    const scores = results.map((r) => r.score as number);
    expect(scores).toEqual([...scores].sort((x, y) => y - x));
  });

  test("respects topK", () => {
    const results = bm25Score(candidates, tokenizeBm25("python agent"), 1);
    expect(results).toHaveLength(1);
  });

  test("all-empty documents yield no results", () => {
    const empties = [
      { id: "x", payload: {}, tokens: tokenizeBm25("") },
      { id: "y", payload: {}, tokens: tokenizeBm25("") },
    ];
    expect(bm25Score(empties, ["python"], 5)).toEqual([]);
  });
});

describe("ChromaDB.generateWhereClause", () => {
  test("returns undefined for empty filters", () => {
    expect(whereClause({})).toBeUndefined();
    expect(whereClause(undefined)).toBeUndefined();
  });

  test("simple equality", () => {
    expect(whereClause({ user_id: "alice" })).toEqual({
      user_id: { $eq: "alice" },
    });
  });

  test("wildcard is skipped", () => {
    expect(whereClause({ user_id: "*" })).toBeUndefined();
  });

  test("array value becomes $in", () => {
    expect(whereClause({ user_id: ["a", "b"] })).toEqual({
      user_id: { $in: ["a", "b"] },
    });
  });

  test("comparison operators map to chroma operators", () => {
    expect(whereClause({ score: { gte: 1, lte: 10 } })).toEqual({
      score: { $gte: 1, $lte: 10 },
    });
  });

  test("multiple fields are combined with $and", () => {
    expect(whereClause({ user_id: "alice", agent_id: "bot1" })).toEqual({
      $and: [{ user_id: { $eq: "alice" } }, { agent_id: { $eq: "bot1" } }],
    });
  });

  test("$or is preserved", () => {
    expect(
      whereClause({ $or: [{ user_id: "alice" }, { user_id: "bob" }] }),
    ).toEqual({
      $or: [{ user_id: { $eq: "alice" } }, { user_id: { $eq: "bob" } }],
    });
  });

  test("$not negates equality to $ne", () => {
    expect(whereClause({ $not: [{ status: "deleted" }] })).toEqual({
      status: { $ne: "deleted" },
    });
  });

  test("$not inverts comparison operators", () => {
    expect(whereClause({ $not: [{ score: { gt: 5 } }] })).toEqual({
      score: { $lte: 5 },
    });
  });
});

describe("ChromaDB.keywordSearch", () => {
  beforeEach(() => {
    mockCollection.get.mockReset();
  });

  const newStore = () =>
    new (ChromaDB as any)({ collectionName: "test" }) as ChromaDB;

  test("scores rows by their lemmatized metadata text", async () => {
    mockCollection.get.mockResolvedValue({
      ids: ["a", "b", "c"],
      metadatas: [
        { textLemmatized: "python memori layer agent" },
        { textLemmatized: "weather forecast today" },
        { textLemmatized: "python agent memori" },
      ],
    });

    const store = newStore();
    const results = await store.keywordSearch!("python memori", 5);

    const ids = (results || []).map((r) => r.id);
    expect(ids).toContain("a");
    expect(ids).toContain("c");
    expect(ids).not.toContain("b");
    for (const r of results || []) {
      expect(r.score).toBeGreaterThan(0);
    }
  });

  test("falls back to the data field when textLemmatized is absent", async () => {
    mockCollection.get.mockResolvedValue({
      ids: ["a"],
      metadatas: [{ data: "python agent" }],
    });

    const store = newStore();
    const results = await store.keywordSearch!("python", 5);
    expect((results || []).map((r) => r.id)).toEqual(["a"]);
  });

  test("returns null when the collection query throws", async () => {
    mockCollection.get.mockRejectedValue(new Error("boom"));
    const store = newStore();
    const results = await store.keywordSearch!("python", 5);
    expect(results).toBeNull();
  });

  test("passes a translated where clause to the collection", async () => {
    mockCollection.get.mockResolvedValue({ ids: [], metadatas: [] });
    const store = newStore();
    await store.keywordSearch!("python", 5, { user_id: "alice" } as any);
    expect(mockCollection.get).toHaveBeenCalledWith(
      expect.objectContaining({ where: { user_id: { $eq: "alice" } } }),
    );
  });
});
