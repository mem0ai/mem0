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
  const { MemoryVectorStore } = require("../src/vector_stores/memory");
  let tmpDir: string;

  beforeEach(() => {
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

  it("constructor does not emit an unhandled rejection when init fails", async () => {
    jest.resetModules();
    jest.doMock("@supabase/supabase-js", () => {
      const failing = {
        from: jest.fn().mockReturnValue({
          insert: jest.fn().mockReturnValue({
            select: jest.fn().mockResolvedValue({
              error: { code: "42P01", message: "no table" },
            }),
          }),
          delete: jest.fn().mockReturnValue({
            eq: jest.fn().mockResolvedValue({ error: null }),
          }),
        }),
      };
      return { createClient: jest.fn().mockReturnValue(failing) };
    });
    const FailingSupabaseDB =
      require("../src/vector_stores/supabase").SupabaseDB;

    const rejections: unknown[] = [];
    const onUnhandled = (reason: unknown) => rejections.push(reason);
    process.on("unhandledRejection", onUnhandled);
    try {
      const store = new FailingSupabaseDB({
        supabaseUrl: "https://example.supabase.co",
        supabaseKey: "fake-key",
        tableName: "memories",
        collectionName: "test",
      });
      expect(store).toBeDefined();
      await new Promise((resolve) => setTimeout(resolve, 25));
    } finally {
      process.removeListener("unhandledRejection", onUnhandled);
    }

    expect(rejections).toEqual([]);
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
// Cassandra — mock client, test interface + idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Cassandra – backward compat with mocked client", () => {
  let CassandraDB: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("cassandra-driver", () => {
      const rows = new Map<
        string,
        { id: string; vector: number[]; payload: string }
      >();
      const memoryRows = () =>
        Array.from(rows.entries())
          .filter(([key]) => key.startsWith("memories:"))
          .map(([, row]) => row);

      class MockClient {
        connect = jest.fn().mockResolvedValue(undefined);

        execute = jest
          .fn()
          .mockImplementation(
            async (
              query: string,
              params: any[] = [],
              options: Record<string, any> = {},
            ) => {
              const normalized = query.replace(/\s+/g, " ").trim();

              if (normalized.startsWith("CREATE KEYSPACE IF NOT EXISTS")) {
                return { rows: [] };
              }

              if (normalized.startsWith("CREATE TABLE IF NOT EXISTS")) {
                return { rows: [] };
              }

              if (
                normalized.startsWith(
                  "INSERT INTO mem0.memories (id, vector, payload) VALUES (?, ?, ?)",
                )
              ) {
                rows.set(`memories:${params[0]}`, {
                  id: params[0],
                  vector: params[1],
                  payload: params[2],
                });
                return { rows: [] };
              }

              if (
                normalized.startsWith(
                  "SELECT id, payload FROM mem0.memories WHERE id = ?",
                )
              ) {
                const row = rows.get(`memories:${params[0]}`);
                return {
                  rows: row ? [{ id: row.id, payload: row.payload }] : [],
                };
              }

              if (
                normalized.startsWith(
                  "SELECT id, vector, payload FROM mem0.memories",
                )
              ) {
                return {
                  rows: memoryRows().map((row) => ({
                    ...row,
                  })),
                };
              }

              if (
                normalized.startsWith("SELECT id, payload FROM mem0.memories")
              ) {
                return {
                  rows: memoryRows().map((row) => ({
                    id: row.id,
                    payload: row.payload,
                  })),
                };
              }

              if (normalized.startsWith("DROP TABLE IF EXISTS mem0.memories")) {
                for (const key of Array.from(rows.keys())) {
                  if (key.startsWith("memories:")) {
                    rows.delete(key);
                  }
                }
                return { rows: [] };
              }

              if (
                normalized.startsWith("DELETE FROM mem0.memories WHERE id = ?")
              ) {
                rows.delete(`memories:${params[0]}`);
                return { rows: [] };
              }

              if (
                normalized.startsWith(
                  "INSERT INTO mem0.memory_migrations (id, user_id) VALUES (?, ?)",
                )
              ) {
                rows.set(`migrations:${params[0]}`, {
                  id: params[0],
                  vector: [0],
                  payload: JSON.stringify({ user_id: params[1] }),
                });
                return { rows: [] };
              }

              if (
                normalized.startsWith(
                  "SELECT user_id FROM mem0.memory_migrations WHERE id = ?",
                )
              ) {
                const row = rows.get(`migrations:${params[0]}`);
                if (!row) {
                  return { rows: [] };
                }
                return {
                  rows: [{ user_id: JSON.parse(row.payload).user_id }],
                };
              }

              throw new Error(
                `Unexpected Cassandra query: ${normalized} prepare=${options.prepare}`,
              );
            },
          );
      }

      return {
        __esModule: true,
        default: {
          Client: jest.fn().mockImplementation(() => new MockClient()),
          auth: {
            PlainTextAuthProvider: jest
              .fn()
              .mockImplementation((username: string, password: string) => ({
                username,
                password,
              })),
          },
        },
      };
    });

    CassandraDB = require("../src/vector_stores/cassandra").CassandraDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new CassandraDB({
      client: {
        execute: jest.fn().mockResolvedValue({ rows: [] }),
      },
      collectionName: "memories",
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
    const cassandraDriver = require("cassandra-driver");
    const store = new CassandraDB({
      contactPoints: ["127.0.0.1"],
      localDataCenter: "datacenter1",
      collectionName: "memories",
      dimension: 3,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();
    await Promise.all([p1, p2, p3]);

    const clientInstance = cassandraDriver.default.Client.mock.results[0].value;
    expect(clientInstance.connect).toHaveBeenCalledTimes(1);
  });

  it("shapes Cassandra writes and normalizes search results", async () => {
    const cassandraDriver = require("cassandra-driver");
    const store = new CassandraDB({
      contactPoints: ["127.0.0.1"],
      localDataCenter: "datacenter1",
      collectionName: "memories",
      dimension: 3,
    });

    await store.initialize();
    await store.insert(
      [[1, 0, 0]],
      ["id-1"],
      [{ user_id: "u1", topic: "alpha" }],
    );

    const clientInstance = cassandraDriver.default.Client.mock.results[0].value;
    expect(clientInstance.execute).toHaveBeenCalledWith(
      expect.stringContaining(
        "INSERT INTO mem0.memories (id, vector, payload)",
      ),
      ["id-1", [1, 0, 0], JSON.stringify({ user_id: "u1", topic: "alpha" })],
      { prepare: true },
    );

    const results = await store.search([1, 0, 0], 5, { user_id: "u1" });
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 1,
      },
    ]);
  });

  it("roundtrips migration user ids", async () => {
    const store = new CassandraDB({
      contactPoints: ["127.0.0.1"],
      localDataCenter: "datacenter1",
      collectionName: "memories",
      dimension: 3,
    });

    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");
  });

  it("supports get, update, delete, and list", async () => {
    const store = new CassandraDB({
      contactPoints: ["127.0.0.1"],
      localDataCenter: "datacenter1",
      collectionName: "memories",
      dimension: 3,
    });

    await store.insert(
      [
        [1, 0, 0],
        [0, 1, 0],
      ],
      ["id-1", "id-2"],
      [
        { user_id: "u1", topic: "alpha" },
        { user_id: "u2", topic: "beta" },
      ],
    );

    expect(await store.get("missing")).toBeNull();
    expect(await store.get("id-1")).toEqual({
      id: "id-1",
      payload: { user_id: "u1", topic: "alpha" },
    });

    await store.update("id-1", [0, 0, 1], {
      user_id: "u1",
      topic: "gamma",
    });
    expect(await store.get("id-1")).toEqual({
      id: "id-1",
      payload: { user_id: "u1", topic: "gamma" },
    });

    const [listed, count] = await store.list({ user_id: "u1" }, 10);
    expect(count).toBe(1);
    expect(listed).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "gamma" },
      },
    ]);

    await store.delete("id-2");
    expect(await store.get("id-2")).toBeNull();

    await store.deleteCol();
    const [afterDrop, afterDropCount] = await store.list(undefined, 10);
    expect(afterDrop).toEqual([]);
    expect(afterDropCount).toBe(0);
  });

  it("scans paged search and list results", async () => {
    const execute = jest
      .fn()
      .mockImplementation(
        async (
          query: string,
          _params: any[] = [],
          options: Record<string, any> = {},
        ) => {
          const normalized = query.replace(/\s+/g, " ").trim();

          if (normalized.startsWith("CREATE KEYSPACE IF NOT EXISTS")) {
            return { rows: [] };
          }

          if (normalized.startsWith("CREATE TABLE IF NOT EXISTS")) {
            return { rows: [] };
          }

          if (
            normalized.startsWith(
              "SELECT id, vector, payload FROM mem0.memories",
            )
          ) {
            if (!options.pageState) {
              return {
                rows: [
                  {
                    id: "id-1",
                    vector: [1, 0, 0],
                    payload: JSON.stringify({ user_id: "u1", topic: "alpha" }),
                  },
                ],
                pageState: "page-2",
              };
            }

            return {
              rows: [
                {
                  id: "id-2",
                  vector: [0, 1, 0],
                  payload: JSON.stringify({ user_id: "u2", topic: "beta" }),
                },
              ],
              pageState: null,
            };
          }

          if (normalized.startsWith("SELECT id, payload FROM mem0.memories")) {
            if (!options.pageState) {
              return {
                rows: [
                  {
                    id: "id-1",
                    payload: JSON.stringify({ user_id: "u1", topic: "alpha" }),
                  },
                ],
                pageState: "page-2",
              };
            }

            return {
              rows: [
                {
                  id: "id-2",
                  payload: JSON.stringify({ user_id: "u2", topic: "beta" }),
                },
              ],
              pageState: null,
            };
          }

          if (
            normalized.startsWith(
              "SELECT user_id FROM mem0.memory_migrations WHERE id = ?",
            )
          ) {
            return { rows: [] };
          }

          throw new Error(`Unexpected Cassandra query: ${normalized}`);
        },
      );
    const store = new CassandraDB({
      client: { execute },
      collectionName: "memories",
      dimension: 3,
    });

    const searchResults = await store.search([1, 0, 0], 5);
    expect(searchResults).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 1,
      },
      {
        id: "id-2",
        payload: { user_id: "u2", topic: "beta" },
        score: 0,
      },
    ]);

    const [listed, count] = await store.list(undefined, 10);
    expect(count).toBe(2);
    expect(listed).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
      },
      {
        id: "id-2",
        payload: { user_id: "u2", topic: "beta" },
      },
    ]);

    expect(execute).toHaveBeenCalledWith(
      expect.stringContaining("SELECT id, vector, payload"),
      [],
      expect.objectContaining({
        autoPage: false,
        fetchSize: 500,
        pageState: undefined,
      }),
    );
    expect(execute).toHaveBeenCalledWith(
      expect.stringContaining("SELECT id, vector, payload"),
      [],
      expect.objectContaining({
        autoPage: false,
        fetchSize: 500,
        pageState: "page-2",
      }),
    );
    expect(execute).toHaveBeenCalledWith(
      expect.stringContaining("SELECT id, payload"),
      [],
      expect.objectContaining({
        autoPage: false,
        fetchSize: 500,
        pageState: "page-2",
      }),
    );
  });

  it("rejects unsafe identifiers", () => {
    expect(
      () =>
        new CassandraDB({
          client: {
            execute: jest.fn().mockResolvedValue({ rows: [] }),
          },
          keyspace: "bad-name",
          collectionName: "memories",
          dimension: 3,
        }),
    ).toThrow("Invalid keyspace");
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 6. S3 Vectors — mock AWS client, test interface + init
// ───────────────────────────────────────────────────────────────────────────
describe("S3 Vectors – backward compat with mocked client", () => {
  function createMockS3VectorsClient(options?: {
    queryDistance?: number;
    queryDistanceMetric?: "cosine" | "euclidean";
  }) {
    const buckets = new Set<string>();
    const indexes = new Map<
      string,
      {
        dimension: number;
        distanceMetric: string;
      }
    >();
    const vectors = new Map<
      string,
      {
        key: string;
        data: { float32: number[] };
        metadata: Record<string, any>;
      }
    >();

    const vectorMapKey = (indexName: string, key: string) =>
      `${indexName}:${key}`;

    return {
      send: jest.fn().mockImplementation(async (command: any) => {
        const name = command.constructor.name;
        const input = command.input;

        switch (name) {
          case "GetVectorBucketCommand":
            if (!buckets.has(input.vectorBucketName)) {
              const error: any = new Error("Bucket not found");
              error.name = "NotFoundException";
              throw error;
            }
            return {};
          case "CreateVectorBucketCommand":
            if (buckets.has(input.vectorBucketName)) {
              const error: any = new Error("Bucket exists");
              error.name = "ConflictException";
              throw error;
            }
            buckets.add(input.vectorBucketName);
            return {};
          case "GetIndexCommand":
            if (!indexes.has(input.indexName)) {
              const error: any = new Error("Index not found");
              error.name = "NotFoundException";
              throw error;
            }
            return {};
          case "CreateIndexCommand":
            if (indexes.has(input.indexName)) {
              const error: any = new Error("Index exists");
              error.name = "ConflictException";
              throw error;
            }
            indexes.set(input.indexName, {
              dimension: input.dimension,
              distanceMetric: input.distanceMetric,
            });
            return {};
          case "PutVectorsCommand":
            for (const vector of input.vectors || []) {
              vectors.set(vectorMapKey(input.indexName, vector.key), {
                key: vector.key,
                data: vector.data,
                metadata: vector.metadata || {},
              });
            }
            return {};
          case "QueryVectorsCommand":
            return {
              distanceMetric: options?.queryDistanceMetric ?? "cosine",
              vectors: [
                {
                  key: "doc-1",
                  metadata: { user_id: "u1", topic: "alpha" },
                  distance: options?.queryDistance ?? 0.25,
                },
              ],
            };
          case "GetVectorsCommand":
            return {
              vectors: (input.keys || [])
                .map((key: string) =>
                  vectors.get(vectorMapKey(input.indexName, key)),
                )
                .filter(Boolean),
            };
          case "DeleteVectorsCommand":
            for (const key of input.keys || []) {
              vectors.delete(vectorMapKey(input.indexName, key));
            }
            return {};
          case "DeleteIndexCommand":
            indexes.delete(input.indexName);
            for (const key of Array.from(vectors.keys())) {
              if (key.startsWith(`${input.indexName}:`)) {
                vectors.delete(key);
              }
            }
            return {};
          case "ListVectorsCommand":
            return {
              vectors: Array.from(vectors.values())
                .filter((entry) =>
                  vectorMapKey(input.indexName, entry.key).startsWith(
                    `${input.indexName}:`,
                  ),
                )
                .map((entry) => ({
                  key: entry.key,
                  metadata: entry.metadata,
                })),
            };
          default:
            throw new Error(`Unexpected S3Vectors command: ${name}`);
        }
      }),
    };
  }

  function findCommandInput(
    client: { send: jest.Mock },
    commandName: string,
  ): Record<string, any> | undefined {
    const match = client.send.mock.calls.find(
      ([command]) => command.constructor.name === commandName,
    );
    return match?.[0]?.input;
  }

  it("implements full VectorStore interface", () => {
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const store = new S3Vectors({
      client: createMockS3VectorsClient(),
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
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
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const mockClient = createMockS3VectorsClient();
    const store = new S3Vectors({
      client: mockClient,
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();

    await Promise.all([p1, p2, p3]);

    expect(
      mockClient.send.mock.calls.filter(
        ([command]) => command.constructor.name === "CreateVectorBucketCommand",
      ),
    ).toHaveLength(1);
    expect(
      mockClient.send.mock.calls.filter(
        ([command]) => command.constructor.name === "CreateIndexCommand",
      ),
    ).toHaveLength(1);
    expect(
      mockClient.send.mock.calls.filter(
        ([command]) => command.constructor.name === "GetVectorBucketCommand",
      ),
    ).toHaveLength(1);
    expect(
      mockClient.send.mock.calls.filter(
        ([command]) => command.constructor.name === "GetIndexCommand",
      ),
    ).toHaveLength(1);
  });

  it("shapes S3 write requests and normalizes search results", async () => {
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const mockClient = createMockS3VectorsClient();
    const store = new S3Vectors({
      client: mockClient,
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
    });

    await store.initialize();
    await store.insert(
      [[0.1, 0.2, 0.3]],
      ["doc-1"],
      [{ user_id: "u1", topic: "alpha" }],
    );

    const putInput = findCommandInput(mockClient, "PutVectorsCommand");
    expect(putInput).toMatchObject({
      vectorBucketName: "test-bucket",
      indexName: "test-index",
      vectors: [
        {
          key: "doc-1",
          data: { float32: [0.1, 0.2, 0.3] },
          metadata: { user_id: "u1", topic: "alpha" },
        },
      ],
    });

    const results = await store.search([0.1, 0.2, 0.3], 5, { user_id: "u1" });

    const queryInput = findCommandInput(mockClient, "QueryVectorsCommand");
    expect(queryInput).toMatchObject({
      vectorBucketName: "test-bucket",
      indexName: "test-index",
      queryVector: { float32: [0.1, 0.2, 0.3] },
      topK: 5,
      filter: { user_id: { $eq: "u1" } },
      returnMetadata: true,
      returnDistance: true,
    });
    expect(results).toEqual([
      {
        id: "doc-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.75,
      },
    ]);
  });

  it("normalizes euclidean distances without collapsing scores to zero", async () => {
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const store = new S3Vectors({
      client: createMockS3VectorsClient({
        queryDistance: 1.5,
        queryDistanceMetric: "euclidean",
      }),
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
      distanceMetric: "cosine",
    });

    const [result] = await store.search([0.1, 0.2, 0.3], 1);

    expect(result).toEqual({
      id: "doc-1",
      payload: { user_id: "u1", topic: "alpha" },
      score: 0.4,
    });
  });

  it("normalizes empty in and nin operands before search hits AWS", async () => {
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const mockClient = createMockS3VectorsClient();
    const store = new S3Vectors({
      client: mockClient,
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
    });

    const baselineQueryCalls = mockClient.send.mock.calls.filter(
      ([command]) => command.constructor.name === "QueryVectorsCommand",
    ).length;
    const emptyInResults = await store.search([0.1, 0.2, 0.3], 5, {
      topic: { in: [] },
    });
    expect(emptyInResults).toEqual([]);
    expect(
      mockClient.send.mock.calls.filter(
        ([command]) => command.constructor.name === "QueryVectorsCommand",
      ),
    ).toHaveLength(baselineQueryCalls);

    await store.search([0.1, 0.2, 0.3], 5, {
      topic: { nin: [] },
    });

    const queryInput = findCommandInput(mockClient, "QueryVectorsCommand");
    expect(queryInput).toMatchObject({
      vectorBucketName: "test-bucket",
      indexName: "test-index",
      queryVector: { float32: [0.1, 0.2, 0.3] },
      topK: 5,
      returnMetadata: true,
      returnDistance: true,
    });
    expect(queryInput.filter).toBeUndefined();
  });
  it("applies client-side list filters, including empty $nin operands", async () => {
    const { S3Vectors } = require("../src/vector_stores/s3_vectors");
    const mockClient = createMockS3VectorsClient();
    const store = new S3Vectors({
      client: mockClient,
      vectorBucketName: "test-bucket",
      collectionName: "test-index",
      embeddingModelDims: 3,
    });

    await store.initialize();
    await store.insert(
      [
        [0.1, 0.2, 0.3],
        [0.3, 0.2, 0.1],
      ],
      ["doc-1", "doc-2"],
      [
        { user_id: "u1", topic: "alpha", tags: ["keep"] },
        { user_id: "u2", topic: "beta", tags: ["skip"] },
      ],
    );

    const [allRows, allCount] = await store.list({ topic: { nin: [] } }, 10);
    expect(allCount).toBe(2);
    expect(allRows.map((row) => row.id)).toEqual(["doc-1", "doc-2"]);

    const [filteredRows, filteredCount] = await store.list(
      {
        $and: [{ topic: { nin: ["beta"] } }, { tags: { in: ["keep"] } }],
      },
      10,
    );

    expect(filteredCount).toBe(1);
    expect(filteredRows).toEqual([
      {
        id: "doc-1",
        payload: { user_id: "u1", topic: "alpha", tags: ["keep"] },
      },
    ]);
  });
});

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
    failPayloadWrite?: boolean;
  }) {
    const nodes = new Map<
      string,
      {
        embedding?: number[];
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

    const extractStructuredArgument = (
      queryString: string,
      key: string,
    ): any => {
      const keyIndex = queryString.indexOf(`${key}:`);
      if (keyIndex < 0) {
        return undefined;
      }

      const objectStart = queryString.indexOf("{", keyIndex);
      if (objectStart < 0) {
        return undefined;
      }

      let depth = 0;
      for (let index = objectStart; index < queryString.length; index += 1) {
        const char = queryString[index];
        if (char === "{") {
          depth += 1;
        } else if (char === "}") {
          depth -= 1;
          if (depth === 0) {
            const literal = queryString.slice(objectStart, index + 1);
            const jsonLiteral = literal.replace(
              /([{\[,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)/g,
              '$1"$2"$3',
            );
            return JSON.parse(jsonLiteral);
          }
        }
      }

      return undefined;
    };

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
          queryString.includes("RETURN success")
        ) {
          const createsNode = queryString.includes("MERGE");
          const processedRows: any[] = [];
          for (const row of parameters.rows) {
            const existing = nodes.get(row.node_id);
            if (!existing && !createsNode) {
              continue;
            }
            nodes.set(row.node_id, {
              embedding: row.embedding,
              labels: existing?.labels || [collectionLabel],
              properties: existing ? existing.properties : {},
            });
            processedRows.push(row);
          }

          if (options?.throwInsertUpsert) {
            throw new Error("Neptune upsert rejected");
          }

          return createMockResponse({
            results: processedRows.map(() => ({
              success: !options?.failInsertUpsert,
            })),
          });
        }

        if (
          queryString.includes("UNWIND $rows AS row") &&
          queryString.includes("SET n += row.properties")
        ) {
          if (!options?.failPayloadWrite) {
            for (const row of parameters.rows || []) {
              const existing = nodes.get(row.node_id);
              nodes.set(row.node_id, {
                embedding: existing?.embedding,
                labels: existing?.labels || [collectionLabel],
                properties: existing
                  ? { ...existing.properties, ...row.properties }
                  : { ...row.properties },
              });
            }
          }

          return createMockResponse({ results: [{ n: {} }] });
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
          const vertexFilter = extractStructuredArgument(
            queryString,
            "vertexFilter",
          );
          const match = [...nodes.entries()].find(([, node]) =>
            matchesFilter(node, vertexFilter),
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
          if (options?.failPayloadWrite) {
            throw new Error("Neptune property write rejected");
          }

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

  it("derives graphIdentifier from a neptune-graph endpoint URI", async () => {
    jest.resetModules();

    const send = jest
      .fn()
      .mockResolvedValue(createMockResponse({ results: [] }));
    const neptuneGraphClient = jest.fn().mockReturnValue({ send });

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
    const store = new NeptuneAnalyticsVectorStore({
      endpoint: "neptune-graph://g-1234567890",
      collectionName: "test",
      dimension: 3,
      region: "us-east-1",
    });

    await store.search([1, 2, 3], 1);

    expect(neptuneGraphClient).toHaveBeenCalledWith({
      region: "us-east-1",
    });
    expect(send).toHaveBeenCalled();
    expect(send.mock.calls[0][0].input.graphIdentifier).toBe("g-1234567890");
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
    const vectorCall = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .find((command: any) =>
        String(command.input.queryString || "").includes(
          "CALL neptune.algo.vectors.upsert",
        ),
      );
    expect(insertCall).toBeDefined();
    expect(insertCall.input.queryString).toContain("MERGE");
    expect(insertCall.input.queryString).not.toContain("FOREACH");
    expect(insertCall.input.parameters.rows[0].properties.label).toBe(
      "topic-a",
    );
    expect(insertCall.input.parameters.rows[0].embedding).toEqual([1, 2, 3]);

    expect(vectorCall).toBeDefined();
    expect(vectorCall.input.queryString).toContain(
      "CALL neptune.algo.vectors.upsert",
    );
    expect(vectorCall.input.queryString).toContain(
      "WITH n, row.embedding AS embedding",
    );
    expect(vectorCall.input.queryString).not.toContain("MERGE");

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
    const searchQuery = String(searchCall[0].input.queryString || "").replace(
      /\s+/g,
      " ",
    );
    expect(searchQuery).toContain("topK.byEmbedding");
    expect(searchCall[0].input.parameters).toBeUndefined();
    expect(searchQuery).toContain("topK: 1");
    expect(searchQuery).toContain("embedding: [1, 2, 3]");
    expect(searchQuery).toContain(
      'property: "~label", value: "MEM0_VECTOR_test"',
    );
    expect(searchQuery).toContain('property: "user_id", value: "u2"');
    expect(searchQuery).toContain('property: "priority", value: 5');
    expect(searchQuery).toContain(
      'stringContains: { property: "data", value: "alp" }',
    );
  });

  it("escapes adversarial Neptune collection and filter identifiers", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const mockClient = {
      send: jest.fn().mockImplementation(async (command: any) => {
        const queryString = String(command.input.queryString || "");
        if (queryString.includes("RETURN count(n) AS count")) {
          return createMockResponse({ results: [{ count: 0 }] });
        }

        return createMockResponse({ results: [] });
      }),
    };
    const store = new NeptuneAnalyticsVectorStore({
      client: mockClient as any,
      graphIdentifier: "g-1234567890",
      collectionName: "memo`graph",
      dimension: 3,
    });

    await store.list({ "topic`name": ["alpha`1", "beta(2)"] }, 2);
    await store.search([1, 2, 3], 4, {
      "topic`name": { eq: "lookup`value" },
    });

    const listCall = mockClient.send.mock.calls.find(([command]: [any]) =>
      String(command.input.queryString || "").includes("LIMIT $limit"),
    )?.[0];
    const searchCall = mockClient.send.mock.calls.find(([command]: [any]) =>
      String(command.input.queryString || "").includes("topK.byEmbedding"),
    )?.[0];

    expect(listCall).toBeDefined();
    expect(searchCall).toBeDefined();

    const listQuery = String(listCall.input.queryString || "").replace(
      /\s+/g,
      " ",
    );
    const searchQuery = String(searchCall.input.queryString || "").replace(
      /\s+/g,
      " ",
    );

    expect(listQuery).toContain("MATCH (n:`MEM0_VECTOR_memo``graph`)");
    expect(listQuery).toContain("n.`topic``name` IN $filter_in_topic_name_1");
    expect(listCall.input.parameters.filter_in_topic_name_1).toEqual([
      "alpha`1",
      "beta(2)",
    ]);

    expect(searchQuery).toContain("topK.byEmbedding");
    expect(searchQuery).toContain("vertexFilter: {");
    expect(searchQuery).toContain('property: "topic`name"');
    expect(searchQuery).toContain('value: "lookup`value"');
  });

  it("serializes complex list filters into Cypher clauses and parameters", async () => {
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

    await store.list(
      {
        $and: [
          {
            $or: [{ priority: { gte: 5 } }, { data: { startsWith: "alp" } }],
          },
          { $not: [{ archived: true }] },
          { label: { contains: "topic" } },
          { tag: ["a", "b"] },
          { optional: "*" },
        ],
      },
      7,
    );

    const listCall = mockClient.send.mock.calls.find(
      ([command]: [any]) =>
        String(command.input.queryString || "").includes("LIMIT $limit") &&
        String(command.input.queryString || "").includes("RETURN n"),
    )?.[0];
    const countCall = mockClient.send.mock.calls.find(([command]: [any]) =>
      String(command.input.queryString || "").includes(
        "RETURN count(n) AS count",
      ),
    )?.[0];

    expect(listCall).toBeDefined();
    expect(countCall).toBeDefined();

    const listQuery = String(listCall.input.queryString || "").replace(
      /\s+/g,
      " ",
    );
    const countQuery = String(countCall.input.queryString || "").replace(
      /\s+/g,
      " ",
    );

    expect(listQuery).toContain("WHERE (");
    expect(listQuery).toContain("n.`priority` >= $filter_gte_priority_1");
    expect(listQuery).toContain(
      "toString(n.`data`) STARTS WITH $filter_startsWith_data_2",
    );
    expect(listQuery).toContain("NOT (n.`archived` = $filter_archived_3)");
    expect(listQuery).toContain(
      "toString(n.`label`) CONTAINS $filter_contains_label_4",
    );
    expect(listQuery).toContain("n.`tag` IN $filter_in_tag_5");
    expect(listQuery).toContain("n.`optional` IS NOT NULL");
    expect(countQuery).toContain("RETURN count(n) AS count");
    expect(listCall.input.parameters).toEqual({
      filter_gte_priority_1: 5,
      filter_startsWith_data_2: "alp",
      filter_archived_3: true,
      filter_contains_label_4: "topic",
      filter_in_tag_5: ["a", "b"],
      limit: 7,
    });
    expect(countCall.input.parameters).toEqual({
      filter_gte_priority_1: 5,
      filter_startsWith_data_2: "alp",
      filter_archived_3: true,
      filter_contains_label_4: "topic",
      filter_in_tag_5: ["a", "b"],
    });
  });

  it("replaces payloads on update and supports user-id storage", async () => {
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

    const combinedUpdateCalls = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .filter((command: any) =>
        String(command.input.queryString || "").includes(
          "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
        ),
      );
    expect(
      combinedUpdateCalls.some((command: any) =>
        String(command.input.queryString || "").includes(
          "CALL neptune.algo.vectors.upsert",
        ),
      ),
    ).toBe(true);
    expect(
      combinedUpdateCalls.some((command: any) =>
        String(command.input.queryString || "").includes("SET n = $properties"),
      ),
    ).toBe(true);
    expect(
      combinedUpdateCalls.some((command: any) =>
        String(command.input.queryString || "").includes("FOREACH"),
      ),
    ).toBe(false);

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

  it("supports payload-only and vector-only Neptune updates", async () => {
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
      [{ data: "alpha", user_id: "u1", stale: "remove-me" }],
    );

    await store.update("id-1", [], { data: "payload-only", user_id: "u1" });
    expect((await store.get("id-1"))!.payload).toEqual(
      expect.objectContaining({
        data: "payload-only",
        user_id: "u1",
      }),
    );

    await store.update("id-1", [3, 2, 1], {});
    expect((await store.get("id-1"))!.payload).toEqual(
      expect.objectContaining({
        data: "payload-only",
        user_id: "u1",
      }),
    );

    const updateCalls = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .filter((command: any) =>
        String(command.input.queryString || "").includes(
          "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
        ),
      );
    expect(
      updateCalls.some((command: any) =>
        String(command.input.queryString || "").includes("SET n = $properties"),
      ),
    ).toBe(true);
    expect(
      updateCalls.some(
        (command: any) =>
          String(command.input.queryString || "").includes(
            "CALL neptune.algo.vectors.upsert",
          ) && !("properties" in (command.input.parameters || {})),
      ),
    ).toBe(true);
  });

  it("deletes the full Neptune collection with deleteCol()", async () => {
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

    await store.deleteCol();

    const [listed, count] = await store.list({ user_id: "u1" });
    expect(listed).toEqual([]);
    expect(count).toBe(0);

    const deleteColCall = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .find((command: any) =>
        String(command.input.queryString || "").includes(
          "MATCH (n:`MEM0_VECTOR_test`)",
        ),
      );
    expect(deleteColCall).toBeDefined();
    expect(deleteColCall.input.queryString).toContain("DETACH DELETE n");
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

    // The payload write runs before the vector upsert, so it is already
    // durable by the time the vector step rejects — the caller's new
    // metadata must not be silently dropped just because the embedding
    // failed to update afterward.
    const afterFailedUpsert = await store.get("id-1");
    expect(afterFailedUpsert).not.toBeNull();
    expect(afterFailedUpsert!.payload).toEqual(
      expect.objectContaining({
        data: "beta",
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

  it("does not leave a phantom record when the property write fails", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient({ failPayloadWrite: true }),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await store.insert(
      [[1, 2, 3]],
      ["id-1"],
      [{ data: "alpha", user_id: "u1" }],
    );

    const results = await store.search([1, 2, 3], 1);
    expect(results).toEqual([]);
  });

  it("does not make the embedding durable when the update payload write fails", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const mockClient = createMockNeptuneClient({ failPayloadWrite: true });
    const store = new NeptuneAnalyticsVectorStore({
      client: mockClient,
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await expect(
      store.update("id-1", [3, 2, 1], { data: "beta", user_id: "u1" }),
    ).rejects.toThrow();

    const upsertCalls = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .filter((command: any) =>
        String(command.input.queryString || "").includes(
          "neptune.algo.vectors.upsert",
        ),
      );
    expect(upsertCalls).toHaveLength(0);
  });

  it("writes the Neptune payload before the vector on a combined update", async () => {
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
      [{ data: "alpha", user_id: "u1" }],
    );

    await store.update("id-1", [3, 2, 1], { data: "beta", user_id: "u1" });

    const updateQueries = mockClient.send.mock.calls
      .map(([command]: [any]) => command)
      .filter((command: any) =>
        String(command.input.queryString || "").includes(
          "MATCH (n:`MEM0_VECTOR_test` {`~id`: $vectorId})",
        ),
      )
      .map((command: any) => String(command.input.queryString || ""));

    const payloadIndex = updateQueries.findIndex((queryString: string) =>
      queryString.includes("SET n = $properties"),
    );
    const vectorIndex = updateQueries.findIndex((queryString: string) =>
      queryString.includes("CALL neptune.algo.vectors.upsert"),
    );

    expect(payloadIndex).toBeGreaterThanOrEqual(0);
    expect(vectorIndex).toBeGreaterThan(payloadIndex);
  });

  it("throws for unsupported Neptune search and list filter shapes", async () => {
    const {
      NeptuneAnalyticsVectorStore,
    } = require("../src/vector_stores/neptune_analytics");
    const store = new NeptuneAnalyticsVectorStore({
      client: createMockNeptuneClient(),
      graphIdentifier: "g-1234567890",
      collectionName: "test",
      dimension: 3,
    });

    await expect(store.search([1, 2, 3], 1, { optional: "*" })).rejects.toThrow(
      "Neptune Analytics vector search does not support property-existence filters.",
    );
    await expect(
      store.search([1, 2, 3], 1, { data: { icontains: "alp" } }),
    ).rejects.toThrow(
      "Neptune Analytics vector search does not support case-insensitive contains filters.",
    );
    await expect(
      store.search([1, 2, 3], 1, { data: { regex: "alp" } }),
    ).rejects.toThrow("Unsupported Neptune Analytics filter operator: regex");
    await expect(
      store.search([1, 2, 3], 1, {
        $not: [{ data: { contains: "alp" } }],
      }),
    ).rejects.toThrow(
      "Neptune Analytics cannot negate this filter shape for vector search.",
    );
    await expect(
      store.search([1, 2, 3], 1, { data: { eq: () => "alp" } }),
    ).rejects.toThrow(
      "Unsupported Neptune Analytics algorithm value type: function",
    );
    await expect(store.list({ data: { icontains: "alp" } })).rejects.toThrow(
      "Neptune Analytics list filters do not support case-insensitive contains filters.",
    );
    await expect(store.list({ data: { regex: "alp" } })).rejects.toThrow(
      "Unsupported Neptune Analytics filter operator: regex",
    );
  });
});

// ───────────────────────────────────────────────────────────────────────────
// ───────────────────────────────────────────────────────────────────────────
// 7. Vectorize — mock Cloudflare client, test idempotent init
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
// 8. AzureMySQL — mock mysql2 pool, test interface + idempotent init + CRUD
// ───────────────────────────────────────────────────────────────────────────
describe("AzureMySQL – backward compat with mocked client", () => {
  let AzureMySQLDB: any;
  let mockPool: any;

  beforeEach(() => {
    jest.resetModules();

    const rows = new Map<
      string,
      { id: string; vector: string; payload: string }
    >();
    let userId: string | null = null;

    mockPool = {
      execute: jest
        .fn()
        .mockImplementation(async (sql: string, params?: any[]) => {
          const q = sql.trim().toUpperCase();

          if (
            q.startsWith("CREATE TABLE") ||
            q.startsWith("CREATE FULLTEXT") ||
            q.startsWith("DROP TABLE")
          ) {
            return [{ affectedRows: 0 }, []];
          }

          // INSERT into main table (ON DUPLICATE KEY)
          if (q.startsWith("INSERT INTO `") && q.includes("ON DUPLICATE KEY")) {
            const [id, vector, payload] = params!;
            rows.set(id, { id, vector, payload });
            return [{ affectedRows: 1 }, []];
          }

          // INSERT into memory_migrations
          if (q.startsWith("INSERT INTO MEMORY_MIGRATIONS")) {
            userId = params![0];
            return [{ affectedRows: 1 }, []];
          }

          // SELECT id, payload FROM table WHERE id = ? (single-row get by PK)
          if (
            q.startsWith("SELECT ID, PAYLOAD FROM") &&
            q.includes("WHERE ID = ?")
          ) {
            const row = rows.get(params![0]);
            return [row ? [row] : [], []];
          }

          // SELECT id, vector, payload FROM table (search with optional filters)
          if (q.startsWith("SELECT ID, VECTOR, PAYLOAD FROM")) {
            return [[...rows.values()], []];
          }

          if (q.includes("MATCH(TEXT_LEMMATIZED) AGAINST")) {
            const term = String(params?.[0] ?? "").toLowerCase();
            const limit = Number(params?.[params!.length - 1] ?? rows.size);
            const matched = [...rows.values()]
              .filter((row) => {
                const payload = JSON.parse(row.payload);
                return String(payload.textLemmatized ?? "")
                  .toLowerCase()
                  .includes(term);
              })
              .slice(0, limit)
              .map((row) => ({ ...row, score: 1 }));
            return [matched, []];
          }

          // SELECT id, payload FROM table (list with LIMIT)
          if (q.startsWith("SELECT ID, PAYLOAD FROM")) {
            return [
              [...rows.values()].slice(0, params![params!.length - 1]),
              [],
            ];
          }

          // SELECT COUNT(*)
          if (q.startsWith("SELECT COUNT(*)")) {
            return [[{ cnt: rows.size }], []];
          }

          // UPDATE
          if (q.startsWith("UPDATE `")) {
            const [vector, payload, id] = params!;
            if (rows.has(id)) {
              rows.set(id, { id, vector, payload });
            }
            return [{ affectedRows: 1 }, []];
          }

          // DELETE
          if (q.startsWith("DELETE FROM `")) {
            rows.delete(params![0]);
            return [{ affectedRows: 1 }, []];
          }

          // SELECT user_id FROM memory_migrations
          if (q.startsWith("SELECT USER_ID FROM MEMORY_MIGRATIONS")) {
            return [userId ? [{ user_id: userId }] : [], []];
          }

          return [[], []];
        }),
      getConnection: jest.fn().mockImplementation(async () => ({
        beginTransaction: jest.fn().mockResolvedValue(undefined),
        execute: jest
          .fn()
          .mockImplementation(async (sql: string, params?: any[]) => {
            return mockPool.execute(sql, params);
          }),
        commit: jest.fn().mockResolvedValue(undefined),
        rollback: jest.fn().mockResolvedValue(undefined),
        release: jest.fn(),
      })),
      end: jest.fn().mockResolvedValue(undefined),
    };

    jest.doMock("mysql2/promise", () => ({
      createPool: jest.fn().mockReturnValue(mockPool),
    }));

    AzureMySQLDB = require("../src/vector_stores/azure_mysql").AzureMySQLDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.keywordSearch).toBe("function");
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
    const mysql2 = require("mysql2/promise");
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();
    await Promise.all([p1, p2, p3]);

    // createPool called only once despite 3 initialize() calls
    expect(mysql2.createPool).toHaveBeenCalledTimes(1);
  });

  it("full CRUD cycle", async () => {
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
    });
    await store.initialize();

    const vec1 = [1, 0, 0, 0];
    const vec2 = [0, 1, 0, 0];

    // Insert
    await store.insert(
      [vec1, vec2],
      ["id-1", "id-2"],
      [{ data: "alpha" }, { data: "beta" }],
    );

    // Get
    const item = await store.get("id-1");
    expect(item).not.toBeNull();
    expect(item!.id).toBe("id-1");

    // Search — vec1 should rank first
    const results = await store.search(vec1, 2);
    expect(results.length).toBeGreaterThan(0);

    // Update
    await store.update("id-1", [0, 0, 1, 0], { data: "updated" });

    // List
    const [listed, count] = await store.list();
    expect(listed.length).toBeGreaterThan(0);
    expect(count).toBeGreaterThan(0);

    // Delete
    await store.delete("id-2");

    // DeleteCol
    await store.deleteCol();
  });

  it("keywordSearch matches textLemmatized payloads", async () => {
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
    });
    await store.initialize();

    await store.insert(
      [[1, 0, 0, 0]],
      ["id-1"],
      [
        {
          data: "alpha",
          textLemmatized: "alpha normalized",
        },
      ],
    );

    const results = await store.keywordSearch("normalized", 5);
    expect(results).not.toBeNull();
    expect(results![0].id).toBe("id-1");
  });

  it("getUserId and setUserId roundtrip", async () => {
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
    });
    await store.initialize();

    await store.setUserId("custom-user");
    const retrieved = await store.getUserId();
    expect(retrieved).toBe("custom-user");
  });

  it("uses mysql_clear_password semantics for Azure tokens", async () => {
    jest.doMock("@azure/identity", () => ({
      DefaultAzureCredential: jest.fn().mockImplementation(() => ({
        getToken: jest.fn().mockResolvedValue({ token: "aad-token" }),
      })),
    }));

    const mysql2 = require("mysql2/promise");
    const store = new AzureMySQLDB({
      host: "localhost",
      user: "test",
      database: "testdb",
      collectionName: "memories",
      embeddingModelDims: 4,
      useAzureCredential: true,
    });
    await store.initialize();

    const poolConfig = mysql2.createPool.mock.calls[0][0];
    const plugin = poolConfig.authPlugins.mysql_clear_password();
    expect(plugin()).toEqual(Buffer.from("aad-token\0"));
  });

  it("rejects invalid collectionName at construction", () => {
    expect(
      () =>
        new AzureMySQLDB({
          host: "localhost",
          user: "test",
          database: "testdb",
          collectionName: "drop--table",
          embeddingModelDims: 4,
        }),
    ).toThrow("Invalid collectionName");
  });
});

// ───────────────────────────────────────────────────────────────────────────
// 9. Memory class — ensure it works with each provider via mocked factories
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
    const memoryId = "3f0d5b6a-9c1e-4a2b-8d7f-1e2c3a4b5c6d";
    const mockVStore = createMockVectorStore();
    mockVStore.search.mockResolvedValue([
      { id: memoryId, payload: { memory: "test", hash: "h" }, score: 0.9 },
    ]);
    mockVStore.get.mockResolvedValue({
      id: memoryId,
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
          id: memoryId,
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
    const item = await mem.get(memoryId);
    expect(item).toBeDefined();

    // update
    const updateResult = await mem.update(memoryId, { text: "new data" });
    expect(updateResult.message).toBe("Memory updated successfully!");

    // delete
    const deleteResult = await mem.delete(memoryId);
    expect(deleteResult.message).toBe("Memory deleted successfully!");

    // deleteAll
    const deleteAllResult = await mem.deleteAll({ userId: "u1" });
    expect(deleteAllResult.message).toBe("Memories deleted successfully!");

    // history
    const history = await mem.history(memoryId);
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

// ───────────────────────────────────────────────────────────────────────────
// WeaviateDB — mock client, behavioral surface checks
// ───────────────────────────────────────────────────────────────────────────
describe("WeaviateDB – backward compat with mocked client", () => {
  let WeaviateDB: any;
  let mockClient: any;
  let mockCol: any;

  beforeEach(() => {
    jest.resetModules();

    mockCol = {
      data: {
        insertMany: jest.fn().mockResolvedValue({}),
        deleteById: jest.fn().mockResolvedValue({}),
        update: jest.fn().mockResolvedValue({}),
      },
      query: {
        nearVector: jest.fn().mockResolvedValue({ objects: [] }),
        bm25: jest.fn().mockResolvedValue({ objects: [] }),
        fetchObjectById: jest.fn().mockResolvedValue(null),
        fetchObjects: jest.fn().mockResolvedValue({ objects: [] }),
      },
      filter: {
        byProperty: jest
          .fn()
          .mockReturnValue({ equal: jest.fn().mockReturnValue({}) }),
      },
    };

    mockClient = {
      collections: {
        exists: jest.fn().mockResolvedValue(false),
        create: jest.fn().mockResolvedValue({}),
        get: jest.fn().mockReturnValue(mockCol),
        delete: jest.fn().mockResolvedValue({}),
      },
    };

    jest.doMock("weaviate-client", () => ({
      default: {
        connectToLocal: jest.fn().mockResolvedValue(mockClient),
        connectToWeaviateCloud: jest.fn().mockResolvedValue(mockClient),
        connectToCustom: jest.fn().mockResolvedValue(mockClient),
        ApiKey: jest.fn().mockReturnValue({}),
        configure: {
          vectorizer: { none: jest.fn().mockReturnValue({}) },
          vectorIndex: { hnsw: jest.fn().mockReturnValue({}) },
        },
      },
      Filters: { and: jest.fn().mockReturnValue({ __mock: "filter" }) },
      __esModule: true,
    }));

    WeaviateDB = require("../src/vector_stores/weaviate").WeaviateDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new WeaviateDB({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
    });
    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.keywordSearch).toBe("function");
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
    const store = new WeaviateDB({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
    });
    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();
    await Promise.all([p1, p2, p3]);
    expect(mockClient.collections.create).toHaveBeenCalledTimes(1);
  });

  it("insert shapes insertMany request correctly", async () => {
    const store = new WeaviateDB({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 3,
    });
    await store.initialize();
    await store.insert([[0.1, 0.2, 0.3]], ["id-1"], [{ data: "hello" }]);
    expect(mockCol.data.insertMany).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          id: "id-1",
          properties: { data: "hello" },
          vectors: [0.1, 0.2, 0.3],
        }),
      ]),
    );
  });

  it("search normalizes nearVector result to id/payload/score", async () => {
    mockCol.query.nearVector.mockResolvedValue({
      objects: [
        {
          uuid: "id-1",
          properties: { data: "x" },
          metadata: { distance: 0.2 },
        },
      ],
    });
    const store = new WeaviateDB({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 3,
    });
    await store.initialize();
    const results = await store.search([0.1, 0.2, 0.3], 1);
    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      id: "id-1",
      payload: { data: "x" },
      score: 0.8,
    });
  });

  it("getUserId / setUserId roundtrip", async () => {
    const store = new WeaviateDB({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
    });
    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");
  });
});
