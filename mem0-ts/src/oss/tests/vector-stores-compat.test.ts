/// <reference types="jest" />
/**
 * Backward-compatibility tests for ALL vector store implementations.
 *
 * Verifies that:
 *  1. Every store implements the full VectorStore interface
 *  2. initialize() is idempotent (safe to call multiple times)
 *  3. Constructor + explicit initialize() doesn't break (the double-call pattern)
 *  4. All CRUD methods work correctly after initialization
 *  5. getUserId / setUserId work correctly
 *  6. The Memory class works with each store via mocked factories
 */

import * as fs from "fs";
import * as path from "path";
import * as os from "os";

jest.setTimeout(15000);

// ───────────────────────────────────────────────────────────────────────────
// 1. MemoryVectorStore — full CRUD, no external dependencies
// ───────────────────────────────────────────────────────────────────────────
describe("MemoryVectorStore – full backward compat", () => {
  let MemoryVectorStore: any;
  let tmpDir: string;

  beforeEach(() => {
    MemoryVectorStore =
      require("../src/vector_stores/memory").MemoryVectorStore;
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-vs-compat-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("implements full VectorStore interface", () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });
    await store.initialize();
    await store.initialize();
    await store.initialize();
    // Insert should still work after multiple initializations
    const vec = new Array(1536).fill(0.1);
    await store.insert([vec], ["id-1"], [{ data: "test" }]);
    const result = await store.get("id-1");
    expect(result).not.toBeNull();
  });

  it("full CRUD cycle with default dimension 1536", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const vec1 = new Array(1536).fill(0);
    vec1[0] = 1.0;
    const vec2 = new Array(1536).fill(0);
    vec2[1] = 1.0;

    // Insert
    await store.insert(
      [vec1, vec2],
      ["id-1", "id-2"],
      [
        { data: "alpha", userId: "u1" },
        { data: "beta", userId: "u1" },
      ],
    );

    // Get
    const item = await store.get("id-1");
    expect(item).not.toBeNull();
    expect(item!.payload.data).toBe("alpha");

    // Search
    const results = await store.search(vec1, 2);
    expect(results.length).toBe(2);
    expect(results[0].id).toBe("id-1");

    // Search with filters (camelCase in payload is normalized to snake_case)
    const filtered = await store.search(vec1, 2, { user_id: "u1" });
    expect(filtered.length).toBe(2);

    // Update
    const vec3 = new Array(1536).fill(0);
    vec3[2] = 1.0;
    await store.update("id-1", vec3, { data: "updated", user_id: "u1" });
    const updated = await store.get("id-1");
    expect(updated!.payload.data).toBe("updated");

    // List
    const [listed, count] = await store.list({ user_id: "u1" });
    expect(count).toBe(2);

    // List with limit
    const [limitedList] = await store.list(undefined, 1);
    expect(limitedList.length).toBe(1);

    // Delete
    await store.delete("id-2");
    const deleted = await store.get("id-2");
    expect(deleted).toBeNull();

    // DeleteCol + re-init
    await store.deleteCol();
    const [afterDelete] = await store.list();
    expect(afterDelete.length).toBe(0);
  });

  it("full CRUD cycle with custom dimension 768", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 768,
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const vec = new Array(768).fill(0.1);
    await store.insert([vec], ["id-1"], [{ data: "test" }]);
    const result = await store.get("id-1");
    expect(result!.payload.data).toBe("test");

    const searchResults = await store.search(vec, 1);
    expect(searchResults.length).toBe(1);
  });

  it("rejects dimension mismatch on insert", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 1536,
      dbPath: path.join(tmpDir, "vs.db"),
    });
    await expect(
      store.insert([new Array(768).fill(0)], ["id-1"], [{}]),
    ).rejects.toThrow("Vector dimension mismatch");
  });

  it("rejects dimension mismatch on search", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 1536,
      dbPath: path.join(tmpDir, "vs.db"),
    });
    await expect(store.search(new Array(768).fill(0), 1)).rejects.toThrow(
      "Query dimension mismatch",
    );
  });

  it("rejects dimension mismatch on update", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dimension: 1536,
      dbPath: path.join(tmpDir, "vs.db"),
    });
    await expect(
      store.update("id-1", new Array(768).fill(0), {}),
    ).rejects.toThrow("Vector dimension mismatch");
  });

  it("getUserId and setUserId roundtrip", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });

    const auto = await store.getUserId();
    expect(typeof auto).toBe("string");
    expect(auto.length).toBeGreaterThan(0);

    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");

    // Overwrite
    await store.setUserId("another-user");
    expect(await store.getUserId()).toBe("another-user");
  });

  it("get returns null for non-existent ID", async () => {
    const store = new MemoryVectorStore({
      collectionName: "test",
      dbPath: path.join(tmpDir, "vs.db"),
    });
    const result = await store.get("non-existent");
    expect(result).toBeNull();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 2. Qdrant — mock QdrantClient, test interface + idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Qdrant – backward compat with mocked client", () => {
  function createMockQdrantClient() {
    const collections = new Map<string, number>();
    const points = new Map<
      string,
      { id: string; vector: number[]; payload: any }
    >();

    return {
      _collections: collections,
      _points: points,
      createCollection: jest
        .fn()
        .mockImplementation(async (name: string, opts: any) => {
          if (collections.has(name)) {
            const err: any = new Error("Collection already exists");
            err.status = 409;
            throw err;
          }
          collections.set(name, opts.vectors.size);
        }),
      getCollection: jest.fn().mockImplementation(async (name: string) => {
        if (!collections.has(name)) {
          const err: any = new Error("Not found");
          err.status = 404;
          throw err;
        }
        return {
          config: { params: { vectors: { size: collections.get(name) } } },
        };
      }),
      getCollections: jest.fn().mockResolvedValue({
        collections: [],
      }),
      upsert: jest
        .fn()
        .mockImplementation(async (collName: string, opts: any) => {
          for (const pt of opts.points) {
            points.set(`${collName}:${pt.id}`, {
              id: pt.id,
              vector: pt.vector,
              payload: pt.payload,
            });
          }
        }),
      retrieve: jest
        .fn()
        .mockImplementation(async (collName: string, opts: any) => {
          const results = [];
          for (const id of opts.ids) {
            const pt = points.get(`${collName}:${id}`);
            if (pt) results.push({ id: pt.id, payload: pt.payload });
          }
          return results;
        }),
      search: jest
        .fn()
        .mockImplementation(async (collName: string, opts: any) => {
          const results: any[] = [];
          points.forEach((pt, key) => {
            if (key.startsWith(`${collName}:`)) {
              results.push({ id: pt.id, payload: pt.payload, score: 0.9 });
            }
          });
          return results.slice(0, opts.limit);
        }),
      scroll: jest
        .fn()
        .mockImplementation(async (collName: string, opts: any) => {
          const results: any[] = [];
          points.forEach((pt, key) => {
            if (key.startsWith(`${collName}:`)) {
              results.push({ id: pt.id, payload: pt.payload });
            }
          });
          return { points: results.slice(0, opts.limit) };
        }),
      delete: jest
        .fn()
        .mockImplementation(async (collName: string, opts: any) => {
          for (const id of opts.points) {
            points.delete(`${collName}:${id}`);
          }
        }),
      deleteCollection: jest.fn().mockImplementation(async (name: string) => {
        collections.delete(name);
      }),
    };
  }

  it("implements full VectorStore interface", () => {
    const { Qdrant } = require("../src/vector_stores/qdrant");
    const store = new Qdrant({
      client: createMockQdrantClient(),
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const { Qdrant } = require("../src/vector_stores/qdrant");
    const mockClient = createMockQdrantClient();
    const store = new Qdrant({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    // Constructor already fires initialize()
    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();

    await Promise.all([p1, p2, p3]);

    // createCollection called only once per collection despite multiple initialize() calls
    expect(mockClient.createCollection).toHaveBeenCalledTimes(2); // test + memory_migrations
  });

  it("full CRUD cycle", async () => {
    const { Qdrant } = require("../src/vector_stores/qdrant");
    const mockClient = createMockQdrantClient();
    const store = new Qdrant({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });
    await store.initialize();

    // Insert
    await store.insert(
      [
        [1, 2, 3],
        [4, 5, 6],
      ],
      ["id-1", "id-2"],
      [{ data: "alpha" }, { data: "beta" }],
    );
    expect(mockClient.upsert).toHaveBeenCalled();

    // Get
    const item = await store.get("id-1");
    expect(item).not.toBeNull();
    expect(item!.payload.data).toBe("alpha");

    // Search
    const results = await store.search([1, 2, 3], 2);
    expect(results.length).toBeGreaterThan(0);

    // Update
    await store.update("id-1", [7, 8, 9], { data: "updated" });

    // List
    const [listed, count] = await store.list();
    expect(listed.length).toBeGreaterThan(0);

    // Delete
    await store.delete("id-2");

    // DeleteCol
    await store.deleteCol();
    expect(mockClient.deleteCollection).toHaveBeenCalledWith("test");
  });

  it("getUserId and setUserId roundtrip", async () => {
    const { Qdrant } = require("../src/vector_stores/qdrant");
    const mockClient = createMockQdrantClient();
    const store = new Qdrant({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });
    await store.initialize();

    const userId = await store.getUserId();
    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);

    await store.setUserId("custom-user");
    const updated = await store.getUserId();
    expect(updated).toBe("custom-user");
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 3. Redis — mock redis client, test interface + idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Redis – backward compat with mocked client", () => {
  let RedisDB: any;

  beforeEach(() => {
    jest.resetModules();

    // Mock redis createClient
    jest.doMock("redis", () => {
      const store = new Map<string, any>();
      const mockClient = {
        connect: jest.fn().mockResolvedValue(undefined),
        on: jest.fn(),
        isOpen: false,
        moduleList: jest
          .fn()
          .mockResolvedValue([["name", "search", "ver", 20000]]),
        ft: {
          dropIndex: jest.fn().mockResolvedValue(undefined),
          create: jest.fn().mockResolvedValue(undefined),
          search: jest.fn().mockResolvedValue({ total: 0, documents: [] }),
        },
        hSet: jest.fn().mockImplementation(async (key: string, obj: any) => {
          store.set(key, obj);
        }),
        hGetAll: jest.fn().mockImplementation(async (key: string) => {
          return store.get(key) || {};
        }),
        del: jest.fn().mockImplementation(async (key: string) => {
          store.delete(key);
        }),
        keys: jest.fn().mockResolvedValue([]),
        quit: jest.fn().mockResolvedValue(undefined),
      };

      // Track connect calls for assertion
      mockClient.connect.mockImplementation(async () => {
        mockClient.isOpen = true;
      });

      return {
        createClient: jest.fn().mockReturnValue(mockClient),
        SchemaFieldTypes: {
          VECTOR: "VECTOR",
          TAG: "TAG",
          TEXT: "TEXT",
          NUMERIC: "NUMERIC",
        },
        VectorAlgorithms: {
          FLAT: "FLAT",
          HNSW: "HNSW",
        },
        __mockClient: mockClient,
      };
    });

    RedisDB = require("../src/vector_stores/redis").RedisDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new RedisDB({
      collectionName: "test",
      embeddingModelDims: 768,
      redisUrl: "redis://localhost:6379",
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const redis = require("redis");
    const mockClient = redis.__mockClient;

    const store = new RedisDB({
      collectionName: "test",
      embeddingModelDims: 768,
      redisUrl: "redis://localhost:6379",
    });

    // Constructor already fires initialize()
    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();

    await Promise.all([p1, p2, p3]);

    // connect() called only once despite multiple initialize() calls
    expect(mockClient.connect).toHaveBeenCalledTimes(1);
  });

  it("constructor + explicit initialize() doesn't double-connect", async () => {
    const redis = require("redis");
    const mockClient = redis.__mockClient;

    const store = new RedisDB({
      collectionName: "test",
      embeddingModelDims: 768,
      redisUrl: "redis://localhost:6379",
    });

    // Explicitly awaiting initialize (what Memory._autoInitialize does)
    await store.initialize();

    // Should only have connected once
    expect(mockClient.connect).toHaveBeenCalledTimes(1);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 4. Supabase — mock Supabase client, test idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Supabase – backward compat with mocked client", () => {
  let SupabaseDB: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("@supabase/supabase-js", () => {
      const mockClient = {
        from: jest.fn().mockReturnValue({
          insert: jest.fn().mockReturnValue({
            select: jest.fn().mockReturnValue({ error: null }),
          }),
          select: jest.fn().mockReturnValue({
            eq: jest.fn().mockReturnValue({ data: [], error: null }),
          }),
          delete: jest.fn().mockReturnValue({
            eq: jest.fn().mockReturnValue({ error: null }),
          }),
          update: jest.fn().mockReturnValue({
            eq: jest.fn().mockReturnValue({ error: null }),
          }),
          upsert: jest.fn().mockReturnValue({ error: null }),
        }),
        rpc: jest.fn().mockResolvedValue({ data: [], error: null }),
      };
      return {
        createClient: jest.fn().mockReturnValue(mockClient),
        __mockClient: mockClient,
      };
    });

    SupabaseDB = require("../src/vector_stores/supabase").SupabaseDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new SupabaseDB({
      supabaseUrl: "https://example.supabase.co",
      supabaseKey: "fake-key",
      tableName: "memories",
      collectionName: "test",
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const store = new SupabaseDB({
      supabaseUrl: "https://example.supabase.co",
      supabaseKey: "fake-key",
      tableName: "memories",
      collectionName: "test",
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    await Promise.all([p1, p2]);
    // No crash = idempotent (Supabase init runs test insert only once)
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 5. AzureAISearch — mock Azure clients, test idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("AzureAISearch – backward compat with mocked client", () => {
  let AzureAISearch: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("@azure/search-documents", () => ({
      SearchClient: jest.fn().mockImplementation(() => ({
        search: jest.fn().mockReturnValue({
          [Symbol.asyncIterator]: () => ({ next: () => ({ done: true }) }),
        }),
        getDocument: jest.fn().mockResolvedValue(null),
        mergeOrUploadDocuments: jest.fn().mockResolvedValue({}),
        deleteDocuments: jest.fn().mockResolvedValue({}),
      })),
      SearchIndexClient: jest.fn().mockImplementation(() => ({
        listIndexes: jest.fn().mockReturnValue({
          [Symbol.asyncIterator]: () => ({ next: () => ({ done: true }) }),
        }),
        createOrUpdateIndex: jest.fn().mockResolvedValue({}),
        deleteIndex: jest.fn().mockResolvedValue({}),
      })),
      AzureKeyCredential: jest
        .fn()
        .mockImplementation((key: string) => ({ key })),
    }));

    jest.doMock("@azure/identity", () => ({
      DefaultAzureCredential: jest.fn(),
    }));

    AzureAISearch =
      require("../src/vector_stores/azure_ai_search").AzureAISearch;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new AzureAISearch({
      serviceName: "test-service",
      collectionName: "test-index",
      apiKey: "fake-key",
      embeddingModelDims: 768,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const store = new AzureAISearch({
      serviceName: "test-service",
      collectionName: "test-index",
      apiKey: "fake-key",
      embeddingModelDims: 768,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();
    await Promise.all([p1, p2, p3]);
    // No crash = idempotent
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 6. Neptune Analytics — mock NeptuneGraph client, test interface + init
// ───────────────────────────────────────────────────────────────────────────
describe("Neptune Analytics – backward compat with mocked client", () => {
  afterEach(() => {
    jest.dontMock("@aws-sdk/client-neptune-graph");
    jest.resetModules();
  });

  function createMockResponse(body: Record<string, any>) {
    return {
      payload: {
        transformToString: jest.fn().mockResolvedValue(JSON.stringify(body)),
      },
    };
  }

  function createMockNeptuneClient(options?: {
    failInsertUpsert?: boolean;
    throwInsertUpsert?: boolean;
    failUpdateUpsert?: boolean;
  }) {
    const nodes = new Map<
      string,
      {
        embedding: number[];
        labels: string[];
        properties: Record<string, any>;
      }
    >();
    let storedUserId: string | undefined;

    const getPropertyValue = (
      node: { labels: string[]; properties: Record<string, any> },
      property: string,
    ) => {
      if (property === "~label") {
        return node.labels;
      }

      return node.properties[property];
    };

    const matchesFilter = (
      node: { labels: string[]; properties: Record<string, any> },
      filter: any,
    ): boolean => {
      if (!filter) {
        return true;
      }

      if (Array.isArray(filter.andAll)) {
        return filter.andAll.every((entry: any) => matchesFilter(node, entry));
      }

      if (Array.isArray(filter.orAll)) {
        return filter.orAll.some((entry: any) => matchesFilter(node, entry));
      }

      const propertyMatcher = (
        property: string,
        predicate: (value: any) => boolean,
      ) => {
        const value = getPropertyValue(node, property);
        if (property === "~label") {
          return (
            Array.isArray(value) && value.some((label) => predicate(label))
          );
        }

        return predicate(value);
      };

      if (filter.equals) {
        return propertyMatcher(
          filter.equals.property,
          (value) => value === filter.equals.value,
        );
      }

      if (filter.notEquals) {
        return propertyMatcher(
          filter.notEquals.property,
          (value) => value !== filter.notEquals.value,
        );
      }

      if (filter.greaterThan) {
        return propertyMatcher(
          filter.greaterThan.property,
          (value) =>
            typeof value === "number" && value > filter.greaterThan.value,
        );
      }

      if (filter.greaterThanOrEquals) {
        return propertyMatcher(
          filter.greaterThanOrEquals.property,
          (value) =>
            typeof value === "number" &&
            value >= filter.greaterThanOrEquals.value,
        );
      }

      if (filter.lessThan) {
        return propertyMatcher(
          filter.lessThan.property,
          (value) => typeof value === "number" && value < filter.lessThan.value,
        );
      }

      if (filter.lessThanOrEquals) {
        return propertyMatcher(
          filter.lessThanOrEquals.property,
          (value) =>
            typeof value === "number" && value <= filter.lessThanOrEquals.value,
        );
      }

      if (filter.in) {
        return propertyMatcher(filter.in.property, (value) =>
          filter.in.value.includes(value),
        );
      }

      if (filter.notIn) {
        return propertyMatcher(
          filter.notIn.property,
          (value) => !filter.notIn.value.includes(value),
        );
      }

      if (filter.stringContains) {
        return propertyMatcher(
          filter.stringContains.property,
          (value) =>
            typeof value === "string" &&
            value.includes(filter.stringContains.value),
        );
      }

      if (filter.startsWith) {
        return propertyMatcher(
          filter.startsWith.property,
          (value) =>
            typeof value === "string" &&
            value.startsWith(filter.startsWith.value),
        );
      }

      return false;
    };

    const toNodeRecord = (
      id: string,
      node: { labels: string[]; properties: Record<string, any> },
    ): Record<string, any> => ({
      "~id": id,
      "~labels": [...node.labels],
      "~properties": { ...node.properties },
    });

    const matchesListParameters = (
      properties: Record<string, any>,
      parameters: Record<string, any>,
    ) =>
      Object.entries(parameters)
        .filter(([key]) => key.startsWith("filter_"))
        .every(([key, value]) => {
          const match = key.match(/^filter_(?:eq_)?(.+)_\d+$/);
          if (!match) {
            return true;
          }

          return properties[match[1]] === value;
        });

    return {
      send: jest.fn().mockImplementation(async (command: any) => {
        const queryString = String(command.input.queryString || "");
        const parameters = command.input.parameters || {};
        const collectionLabelMatch = queryString.match(/MERGE \(n:`([^`]+)`/);
        const collectionLabel = collectionLabelMatch?.[1] || "MEM0_VECTOR_test";

        if (
          queryString.includes("UNWIND $nodeIds AS nodeId") &&
          queryString.includes("RETURN nodeId")
        ) {
          return createMockResponse({
            results: (parameters.nodeIds || [])
              .filter((nodeId: string) => nodes.has(nodeId))
              .map((nodeId: string) => ({ nodeId })),
          });
        }

        if (
          queryString.includes("UNWIND $nodeIds AS nodeId") &&
          queryString.includes("DETACH DELETE n")
        ) {
          for (const nodeId of parameters.nodeIds || []) {
            nodes.delete(nodeId);
          }
          return createMockResponse({ results: [] });
        }

        if (
          queryString.includes("CALL neptune.algo.vectors.upsert") &&
          Array.isArray(parameters.rows) &&
          queryString.includes("SET n += row.properties")
        ) {
          for (const row of parameters.rows) {
            const existing = nodes.get(row.node_id);
            nodes.set(row.node_id, {
              embedding: row.embedding,
              labels: [collectionLabel],
              properties: existing
                ? { ...existing.properties, ...row.properties }
                : { ...row.properties },
            });
          }

          if (options?.throwInsertUpsert) {
            throw new Error("Neptune upsert rejected");
          }

          return createMockResponse({
            results: (parameters.rows || []).map(() => ({
              success: !options?.failInsertUpsert,
            })),
          });
        }

        if (
          queryString.includes("CALL neptune.algo.vectors.upsert") &&
          parameters.vectorId
        ) {
          if (options?.failUpdateUpsert) {
            return createMockResponse({ results: [{ success: false }] });
          }

          const existing = nodes.get(parameters.vectorId);
          if (existing) {
            nodes.set(parameters.vectorId, {
              embedding: parameters.embedding,
              labels: existing.labels,
              properties: parameters.properties || existing.properties,
            });
          }
          return createMockResponse({ results: [{ success: true }] });
        }

        if (queryString.includes("topK.byEmbedding")) {
          const match = [...nodes.entries()].find(([, node]) =>
            matchesFilter(node, parameters.vertexFilter),
          );

          return createMockResponse({
            results: match
              ? [
                  {
                    node: toNodeRecord(match[0], match[1]),
                    score: 0.25,
                  },
                ]
              : [],
          });
        }

        if (queryString.includes("pg_schema")) {
          const labels = new Set<string>();
          for (const node of nodes.values()) {
            for (const label of node.labels) {
              labels.add(label);
            }
          }
          if (storedUserId) {
            labels.add("MEM0_VECTOR_memory_migrations");
          }
          return createMockResponse({
            results: [{ result: [...labels] }],
          });
        }

        if (
          queryString.includes(
            "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
          ) &&
          queryString.includes("RETURN n") &&
          queryString.includes("LIMIT 1")
        ) {
          const node = nodes.get(parameters.vectorId);
          return createMockResponse({
            results: node
              ? [{ n: toNodeRecord(parameters.vectorId, node) }]
              : [],
          });
        }

        if (
          queryString.includes("MATCH (n:`MEM0_VECTOR_test`)") &&
          queryString.includes("RETURN count(n) AS count")
        ) {
          const count = [...nodes.values()].filter((node) =>
            matchesListParameters(node.properties, parameters),
          ).length;

          return createMockResponse({ results: [{ count }] });
        }

        if (
          queryString.includes("MATCH (n:`MEM0_VECTOR_test`)") &&
          queryString.includes("RETURN n") &&
          queryString.includes("LIMIT $limit")
        ) {
          const results = [...nodes.entries()]
            .filter(([, node]) =>
              matchesListParameters(node.properties, parameters),
            )
            .slice(0, parameters.limit || 100)
            .map(([id, node]) => ({ n: toNodeRecord(id, node) }));

          return createMockResponse({ results });
        }

        if (
          queryString.includes(
            "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
          ) &&
          queryString.includes("SET n = $properties")
        ) {
          const existing = nodes.get(parameters.vectorId);
          if (existing) {
            nodes.set(parameters.vectorId, {
              embedding: existing.embedding,
              labels: existing.labels,
              properties: { ...parameters.properties },
            });
          }
          return createMockResponse({ results: [] });
        }

        if (
          queryString.includes(
            "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
          ) &&
          queryString.includes("DETACH DELETE n")
        ) {
          nodes.delete(parameters.vectorId);
          return createMockResponse({ results: [] });
        }

        if (
          queryString.includes("MATCH (n:`MEM0_VECTOR_test`)") &&
          queryString.includes("DETACH DELETE n")
        ) {
          nodes.clear();
          return createMockResponse({ results: [] });
        }

        if (
          queryString.includes("MATCH (n:`MEM0_VECTOR_memory_migrations`") &&
          queryString.includes("RETURN n")
        ) {
          return createMockResponse({
            results: storedUserId
              ? [
                  {
                    n: toNodeRecord(parameters.userNodeId, {
                      labels: ["MEM0_VECTOR_memory_migrations"],
                      properties: {
                        user_id: storedUserId,
                      },
                    }),
                  },
                ]
              : [],
          });
        }

        if (
          queryString.includes("MERGE (n:`MEM0_VECTOR_memory_migrations`") &&
          queryString.includes("SET n.user_id = $userId")
        ) {
          storedUserId = parameters.userId;
          return createMockResponse({ results: [] });
        }

        return createMockResponse({ results: [{ success: true }] });
      }),
    };
  }

  it("implements full VectorStore interface", () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient(),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const mockClient = createMockNeptuneClient();
    const store = new NeptuneAnalyticsVectorStore({
      client: mockClient,
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();

    expect(p1).toBe(p2);
    expect(p2).toBe(p3);

    await Promise.all([p1, p2, p3]);
    expect(mockClient.send).not.toHaveBeenCalled();
  });

  it("passes custom HTTPS endpoints to the AWS client when graphIdentifier is provided", () => {
    jest.resetModules();

    const neptuneGraphClient = jest.fn().mockReturnValue({
      send: jest.fn(),
    });

    jest.doMock("@aws-sdk/client-neptune-graph", () => ({
      ExecuteQueryCommand: class ExecuteQueryCommand {
        input: any;

        constructor(input: any) {
          this.input = input;
        }
      },
      NeptuneGraphClient: neptuneGraphClient,
    }));

    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");

    new NeptuneAnalyticsVectorStore({
      graphIdentifier: "g-1234567890",
      endpoint: "https://example.us-east-1.neptune-graph.amazonaws.com",
      collectionName: "test",
      dimension: 3,
      region: "us-east-1",
      profile: "dev-profile",
      maxAttempts: 3,
    });

    expect(neptuneGraphClient).toHaveBeenCalledWith({
      endpoint: "https://example.us-east-1.neptune-graph.amazonaws.com",
      maxAttempts: 3,
      profile: "dev-profile",
      region: "us-east-1",
    });
  });

  it("rejects HTTPS endpoints without an explicit graphIdentifier", () => {
    jest.resetModules();

    jest.doMock("@aws-sdk/client-neptune-graph", () => ({
      ExecuteQueryCommand: class ExecuteQueryCommand {
        input: any;

        constructor(input: any) {
          this.input = input;
        }
      },
      NeptuneGraphClient: jest.fn().mockReturnValue({
        send: jest.fn(),
      }),
    }));

    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");

    expect(
      () =>
        new NeptuneAnalyticsVectorStore({
          endpoint: "https://example.us-east-1.neptune-graph.amazonaws.com",
          collectionName: "test",
          dimension: 3,
        }),
    ).toThrow(
      "Neptune Analytics HTTPS endpoints require graphIdentifier; pass graphIdentifier separately or use neptune-graph://<graph-id>.",
    );
  });

  it("shapes Neptune write requests and normalizes search results", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const mockClient = createMockNeptuneClient();
    const store = new NeptuneAnalyticsVectorStore({
      client: mockClient,
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.insert(
      [[1, 2, 3]],
      ["id-1"],
      [{ data: "alpha", label: "topic-a", priority: 7, user_id: "u1" }],
    );

    expect(mockClient.send).toHaveBeenCalled();
    const insertCall = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .find((command: any) =>
        String(command.input.queryString || "").includes("MERGE"),
      );
    expect(insertCall).toBeDefined();
    expect(insertCall.input.queryString).toContain("MERGE");
    expect(insertCall.input.queryString).toContain(
      "CALL neptune.algo.vectors.upsert",
    );
    expect(insertCall.input.parameters.rows[0].properties.label).toBe(
      "topic-a",
    );
    expect(insertCall.input.parameters.rows[0].embedding).toEqual([1, 2, 3]);

    const results = await store.search([1, 2, 3], 1, {
      $or: [{ user_id: "u2" }, { priority: { gte: 5 } }],
      data: { contains: "alp" },
    });
    expect(results).toHaveLength(1);
    expect(results[0]).toEqual({
      id: "id-1",
      payload: expect.objectContaining({
        data: "alpha",
        label: "topic-a",
        user_id: "u1",
      }),
      score: 0.8,
    });

    const searchCall =
      mockClient.send.mock.calls[mockClient.send.mock.calls.length - 1];
    expect(searchCall[0].input.queryString).toContain("topK.byEmbedding");
    expect(searchCall[0].input.parameters.vertexFilter).toEqual({
      andAll: [
        {
          equals: {
            property: "~label",
            value: "MEM0_VECTOR_test",
          },
        },
        {
          andAll: [
            {
              orAll: [
                {
                  equals: {
                    property: "user_id",
                    value: "u2",
                  },
                },
                {
                  greaterThanOrEquals: {
                    property: "priority",
                    value: 5,
                  },
                },
              ],
            },
            {
              stringContains: {
                property: "data",
                value: "alp",
              },
            },
          ],
        },
      ],
    });
  });

  it("replaces payloads on update and supports user-id storage", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient(),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.insert(
      [[1, 2, 3]],
      ["id-1"],
      [{ data: "alpha", user_id: "u1", stale: "remove-me" }],
    );

    const created = await store.get("id-1");
    expect(created).not.toBeNull();
    expect(created!.payload).toEqual(
      expect.objectContaining({
        data: "alpha",
        user_id: "u1",
      }),
    );

    await store.update("id-1", [3, 2, 1], { data: "beta", user_id: "u1" });

    const updated = await store.get("id-1");
    expect(updated).not.toBeNull();
    expect(updated!.payload).toEqual(
      expect.objectContaining({
        data: "beta",
        user_id: "u1",
      }),
    );
    expect(updated!.payload.stale).toBeUndefined();

    const [listed, count] = await store.list({ user_id: "u1" });
    expect(count).toBe(1);
    expect(listed[0].id).toBe("id-1");

    const generatedUserId = await store.getUserId();
    expect(typeof generatedUserId).toBe("string");
    expect(generatedUserId.length).toBeGreaterThan(0);

    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");

    await store.delete("id-1");
    expect(await store.get("id-1")).toBeNull();
  });

  it("returns a real total count for list pagination", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient(),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.insert(
      [
        [1, 2, 3],
        [3, 2, 1],
      ],
      ["id-1", "id-2"],
      [
        { data: "alpha", user_id: "u1" },
        { data: "beta", user_id: "u1" },
      ],
    );

    const [listed, count] = await store.list({ user_id: "u1" }, 1);
    expect(listed).toHaveLength(1);
    expect(count).toBe(2);
  });

  it("reads a persisted user id on a fresh store instance", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const mockClient = createMockNeptuneClient();
    const store = new NeptuneAnalyticsVectorStore({
      client: mockClient,
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.setUserId("persisted-user");

    const freshStore = new NeptuneAnalyticsVectorStore({
      client: mockClient,
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    expect(await freshStore.getUserId()).toBe("persisted-user");
  });

  it("throws when Neptune rejects an update upsert", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient({ failUpdateUpsert: true }),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.insert(
      [[1, 2, 3]],
      ["id-1"],
      [{ data: "alpha", user_id: "u1" }],
    );

    await expect(
      store.update("id-1", [3, 2, 1], { data: "beta", user_id: "u1" }),
    ).rejects.toThrow("Update failed in Neptune Analytics");

    const unchanged = await store.get("id-1");
    expect(unchanged).not.toBeNull();
    expect(unchanged!.payload).toEqual(
      expect.objectContaining({
        data: "alpha",
        user_id: "u1",
      }),
    );
  });

  it("does not leave a phantom record when Neptune rejects an insert upsert", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient({ failInsertUpsert: true }),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await expect(
      store.insert([[1, 2, 3]], ["id-1"], [{ data: "alpha", user_id: "u1" }]),
    ).rejects.toThrow("Insert failed in Neptune Analytics");

    expect(await store.get("id-1")).toBeNull();
  });

  it("does not leave a phantom record when Neptune throws during insert upsert", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient({ throwInsertUpsert: true }),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await expect(
      store.insert([[1, 2, 3]], ["id-1"], [{ data: "alpha", user_id: "u1" }]),
    ).rejects.toThrow("Neptune upsert rejected");

    expect(await store.get("id-1")).toBeNull();
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 6. Vectorize — mock Cloudflare client, test idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Vectorize – backward compat with mocked client", () => {
  let VectorizeDB: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("cloudflare", () => {
      const mockIndexes = {
        list: jest.fn().mockReturnValue({
          [Symbol.asyncIterator]: () => ({
            next: async () => ({ done: true }),
          }),
        }),
        create: jest.fn().mockResolvedValue({}),
        delete: jest.fn().mockResolvedValue({}),
        query: jest.fn().mockResolvedValue({ matches: [] }),
        getByIds: jest.fn().mockResolvedValue([]),
        metadataIndex: {
          list: jest.fn().mockResolvedValue({ metadataIndexes: [] }),
          create: jest.fn().mockResolvedValue({}),
        },
      };

      return {
        __esModule: true,
        default: jest.fn().mockImplementation(() => ({
          apiToken: "fake-token",
          vectorize: { indexes: mockIndexes },
          __mockIndexes: mockIndexes,
        })),
      };
    });

    VectorizeDB = require("../src/vector_stores/vectorize").VectorizeDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new VectorizeDB({
      apiKey: "fake-token",
      indexName: "test-index",
      accountId: "test-account",
      dimension: 768,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is idempotent (same promise returned)", async () => {
    const store = new VectorizeDB({
      apiKey: "fake-token",
      indexName: "test-index",
      accountId: "test-account",
      dimension: 768,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    await Promise.all([p1, p2]);
    // No crash = idempotent
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 7. LangchainVectorStore — mock Langchain client, verify no-op init
// ───────────────────────────────────────────────────────────────────────────
describe("LangchainVectorStore – backward compat", () => {
  it("implements full VectorStore interface", () => {
    const { LangchainVectorStore } = require("../src/vector_stores/langchain");
    const mockLcStore = {
      addVectors: jest.fn().mockResolvedValue(undefined),
      similaritySearchVectorWithScore: jest.fn().mockResolvedValue([]),
      delete: jest.fn().mockResolvedValue(undefined),
    };
    const store = new LangchainVectorStore({
      client: mockLcStore,
      collectionName: "test",
      dimension: 768,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
  });

  it("initialize() is a no-op and safe to call multiple times", async () => {
    const { LangchainVectorStore } = require("../src/vector_stores/langchain");
    const mockLcStore = {
      addVectors: jest.fn().mockResolvedValue(undefined),
      similaritySearchVectorWithScore: jest.fn().mockResolvedValue([]),
    };
    const store = new LangchainVectorStore({
      client: mockLcStore,
      collectionName: "test",
    });
    await store.initialize();
    await store.initialize();
    await store.initialize();
  });

  it("insert and search work with mock Langchain client", async () => {
    const { LangchainVectorStore } = require("../src/vector_stores/langchain");
    const mockLcStore = {
      addVectors: jest.fn().mockResolvedValue(undefined),
      similaritySearchVectorWithScore: jest
        .fn()
        .mockResolvedValue([
          [
            { metadata: { _mem0_id: "id-1", data: "test" }, pageContent: "" },
            0.95,
          ],
        ]),
    };
    const store = new LangchainVectorStore({
      client: mockLcStore,
      collectionName: "test",
      dimension: 4,
    });

    await store.insert([[1, 2, 3, 4]], ["id-1"], [{ data: "test" }]);
    expect(mockLcStore.addVectors).toHaveBeenCalled();

    const results = await store.search([1, 2, 3, 4], 1);
    expect(results.length).toBe(1);
    expect(results[0].id).toBe("id-1");
    expect(results[0].score).toBe(0.95);
  });

  it("getUserId and setUserId work (in-memory)", async () => {
    const { LangchainVectorStore } = require("../src/vector_stores/langchain");
    const mockLcStore = {
      addVectors: jest.fn(),
      similaritySearchVectorWithScore: jest.fn(),
    };
    const store = new LangchainVectorStore({
      client: mockLcStore,
      collectionName: "test",
    });

    const defaultId = await store.getUserId();
    expect(defaultId).toBe("anonymous-langchain-user");

    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");
  });

  it("rejects vector dimension mismatch on insert", async () => {
    const { LangchainVectorStore } = require("../src/vector_stores/langchain");
    const mockLcStore = {
      addVectors: jest.fn(),
      similaritySearchVectorWithScore: jest.fn(),
    };
    const store = new LangchainVectorStore({
      client: mockLcStore,
      collectionName: "test",
      dimension: 4,
    });

    await expect(store.insert([[1, 2, 3]], ["id-1"], [{}])).rejects.toThrow(
      "Vector dimension mismatch",
    );
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 8. Memory class — ensure it works with each provider via mocked factories
// ───────────────────────────────────────────────────────────────────────────
describe("Memory class – backward compat with all providers", () => {
  function createMockEmbedder(dims: number) {
    return {
      embed: jest.fn().mockResolvedValue(new Array(dims).fill(0)),
      embedBatch: jest.fn().mockResolvedValue([new Array(dims).fill(0)]),
    };
  }

  function createMockVectorStore() {
    return {
      insert: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([]),
      get: jest.fn().mockResolvedValue(null),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[], 0]),
      getUserId: jest.fn().mockResolvedValue("test-user-id"),
      setUserId: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
  }

  let MemoryClass: any;
  let mockEmbedderFactory: any;
  let mockVectorStoreFactory: any;

  beforeEach(() => {
    jest.resetModules();

    const mockEmbedder = createMockEmbedder(1536);
    const mockVStore = createMockVectorStore();

    mockEmbedderFactory = { create: jest.fn().mockReturnValue(mockEmbedder) };
    mockVectorStoreFactory = { create: jest.fn().mockReturnValue(mockVStore) };

    jest.doMock("../src/utils/factory", () => ({
      EmbedderFactory: mockEmbedderFactory,
      VectorStoreFactory: mockVectorStoreFactory,
      LLMFactory: {
        create: jest.fn().mockReturnValue({
          generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
        }),
      },
      HistoryManagerFactory: {
        create: jest.fn().mockReturnValue({
          addHistory: jest.fn().mockResolvedValue(undefined),
          getHistory: jest.fn().mockResolvedValue([]),
          reset: jest.fn().mockResolvedValue(undefined),
        }),
      },
    }));

    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
      isTelemetryEnabled: jest.fn(() => false),
    }));

    MemoryClass = require("../src/memory").Memory;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("works with explicit dimension (no probe)", async () => {
    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    const embedder = mockEmbedderFactory.create.mock.results[0].value;
    expect(embedder.embed).not.toHaveBeenCalledWith("dimension probe");

    const vsCreateCall = mockVectorStoreFactory.create.mock.calls[0];
    expect(vsCreateCall[1].dimension).toBe(1536);
  });

  it("works with embeddingDims (no probe)", async () => {
    const mem = new MemoryClass({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", embeddingDims: 768 },
      },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    const mockEmbedder768 = createMockEmbedder(768);
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder768);

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockEmbedder768.embed).not.toHaveBeenCalledWith("dimension probe");
  });

  it("probes when no dimension provided", async () => {
    const mockEmbedder768 = createMockEmbedder(768);
    mockEmbedderFactory.create.mockReturnValue(mockEmbedder768);

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "nomic-embed-text" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockEmbedder768.embed).toHaveBeenCalledWith("dimension probe");

    const vsCreateCall = mockVectorStoreFactory.create.mock.calls[0];
    expect(vsCreateCall[1].dimension).toBe(768);
  });

  it("calls vectorStore.initialize() after creation", async () => {
    const mockVStore = createMockVectorStore();
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockVStore.initialize).toHaveBeenCalled();
  });

  it("all public methods work after initialization", async () => {
    const mockVStore = createMockVectorStore();
    mockVStore.search.mockResolvedValue([
      { id: "id-1", payload: { memory: "test", hash: "h" }, score: 0.9 },
    ]);
    mockVStore.get.mockResolvedValue({
      id: "id-1",
      payload: {
        memory: "test",
        hash: "h",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });
    mockVStore.list.mockResolvedValue([
      [
        {
          id: "id-1",
          payload: {
            memory: "test",
            hash: "h",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        },
      ],
      1,
    ]);
    mockVectorStoreFactory.create.mockReturnValue(mockVStore);

    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    // getAll
    const all = await mem.getAll({ filters: { user_id: "u1" } });
    expect(all).toBeDefined();

    // search
    const searchResult = await mem.search("query", {
      filters: { user_id: "u1" },
    });
    expect(searchResult).toBeDefined();

    // get
    const item = await mem.get("id-1");
    expect(item).toBeDefined();

    // update
    const updateResult = await mem.update("id-1", "new data");
    expect(updateResult.message).toBe("Memory updated successfully!");

    // delete
    const deleteResult = await mem.delete("id-1");
    expect(deleteResult.message).toBe("Memory deleted successfully!");

    // deleteAll
    const deleteAllResult = await mem.deleteAll({ userId: "u1" });
    expect(deleteAllResult.message).toBe("Memories deleted successfully!");

    // history
    const history = await mem.history("id-1");
    expect(Array.isArray(history)).toBe(true);
  });

  it("reset re-creates vector store correctly", async () => {
    const mockVStore1 = createMockVectorStore();
    const mockVStore2 = createMockVectorStore();
    mockVectorStoreFactory.create
      .mockReturnValueOnce(mockVStore1)
      .mockReturnValueOnce(mockVStore2);

    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 1536 },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    expect(mockVectorStoreFactory.create).toHaveBeenCalledTimes(1);

    await mem.reset();
    expect(mockVectorStoreFactory.create).toHaveBeenCalledTimes(2);
    // Second store should also have initialize called
    expect(mockVStore2.initialize).toHaveBeenCalled();
  });

  it("propagates init error to public methods", async () => {
    const failingEmbedder = {
      embed: jest.fn().mockRejectedValue(new Error("Embedder unreachable")),
      embedBatch: jest.fn(),
    };
    mockEmbedderFactory.create.mockReturnValue(failingEmbedder);

    const consoleSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const mem = new MemoryClass({
      embedder: { provider: "ollama", config: { model: "test" } },
      vectorStore: { provider: "qdrant", config: { collectionName: "t" } },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await expect(mem.getAll({ filters: { user_id: "u1" } })).rejects.toThrow(
      "auto-detect embedding dimension",
    );
    await expect(
      mem.search("q", { filters: { user_id: "u1" } }),
    ).rejects.toThrow("auto-detect embedding dimension");
    await expect(mem.get("id")).rejects.toThrow(
      "auto-detect embedding dimension",
    );

    consoleSpy.mockRestore();
  });
});
