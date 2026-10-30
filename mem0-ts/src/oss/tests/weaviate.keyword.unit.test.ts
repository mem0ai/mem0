/**
 * Weaviate keyword search must run BM25 against the lemmatized field.
 *
 * The memory layer lemmatizes the query before calling keywordSearch and stores
 * the lemmatized text under `textLemmatized`. Matching a stemmed query against
 * the raw `data` field silently misses hits, so keyword recall degrades.
 */
/// <reference types="jest" />

describe("Weaviate keywordSearch – mocked weaviate-client", () => {
  let WeaviateDB: any;
  let bm25Mock: jest.Mock;

  beforeEach(() => {
    jest.resetModules();
    bm25Mock = jest.fn(async () => ({ objects: [] }));

    jest.doMock("weaviate-client", () => {
      const col = {
        data: { insertMany: jest.fn(async () => undefined) },
        query: {
          bm25: bm25Mock,
          fetchObjectById: jest.fn(async () => null),
          fetchObjects: jest.fn(async () => ({ objects: [] })),
          nearVector: jest.fn(async () => ({ objects: [] })),
        },
        filter: {
          byProperty: (key: string) => ({
            equal: (value: any) => ({ key, value }),
          }),
        },
      };

      const client = {
        collections: {
          exists: jest.fn(async () => false),
          create: jest.fn(async () => undefined),
          get: jest.fn(() => col),
          delete: jest.fn(async () => undefined),
        },
      };

      const weaviateDefault = {
        configure: {
          vectorizer: { none: () => ({}) },
          vectorIndex: { hnsw: () => ({}) },
        },
        connectToLocal: jest.fn(async () => client),
        connectToCustom: jest.fn(async () => client),
      };

      return {
        __esModule: true,
        default: weaviateDefault,
        Filters: { and: (...conditions: any[]) => conditions },
      };
    });

    WeaviateDB = require("../src/vector_stores/weaviate").WeaviateDB;
  });

  afterEach(() => {
    jest.resetModules();
  });

  it("runs BM25 against the lemmatized field, not the raw data field", async () => {
    const store = new WeaviateDB({
      collectionName: "test",
      embeddingModelDims: 4,
      clusterUrl: "http://localhost:8080",
    });

    await store.keywordSearch("studi", 5, { user_id: "alice" });

    expect(bm25Mock).toHaveBeenCalledTimes(1);
    const [, options] = bm25Mock.mock.calls[0];
    expect(options.queryProperties).toEqual(["textLemmatized"]);
    expect(options.queryProperties).not.toContain("data");
  });
});
