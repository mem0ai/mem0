jest.mock("pg", () => {
  throw new Error("Cannot find module 'pg'");
});

jest.mock("natural", () => {
  throw new Error("Cannot find module 'natural'");
});

describe("mem0ai/oss without pg or natural installed", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("mem0ai/oss loads", async () => {
    await expect(import("../src")).resolves.toHaveProperty("Memory");
  });

  test("PGVector explains how to install pg", async () => {
    const { PGVector } = await import("../src/vector_stores/pgvector");
    const store = new PGVector({
      connectionString: "postgresql://localhost:5432/db",
      embeddingModelDims: 3,
    } as any);

    await expect(store.initialize()).rejects.toThrow(
      "The 'pg' package is required to use the PGVector vector store. Install it with: npm install pg",
    );
  });

  test("BM25 lemmatization falls back to the built-in stemmer", async () => {
    const { lemmatizeForBm25 } = await import("../src/utils/lemmatization");

    expect(lemmatizeForBm25("The dogs were running")).toBe("dog runn running");
  });
});
