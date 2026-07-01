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
// 6. Databricks — mock SQL + REST clients, test interface + idempotent init
// ───────────────────────────────────────────────────────────────────────────
describe("Databricks – backward compat with mocked clients", () => {
  let DatabricksVectorStore: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("@databricks/sql", () => {
      let migrationUserId: string | undefined;

      const executeStatement = jest
        .fn()
        .mockImplementation(async (sql: string) => {
          const normalized = sql.replace(/\s+/g, " ").trim();

          if (
            normalized.startsWith("CREATE SCHEMA IF NOT EXISTS") ||
            normalized.startsWith("CREATE TABLE IF NOT EXISTS") ||
            normalized.startsWith("ALTER TABLE main.default.memories")
          ) {
            return {
              fetchAll: jest.fn().mockResolvedValue([]),
              close: jest.fn().mockResolvedValue(undefined),
            };
          }

          if (
            normalized.startsWith(
              "SELECT user_id FROM main.default.memory_migrations LIMIT 1",
            )
          ) {
            return {
              fetchAll: jest
                .fn()
                .mockResolvedValue(
                  migrationUserId ? [{ user_id: migrationUserId }] : [],
                ),
              close: jest.fn().mockResolvedValue(undefined),
            };
          }

          if (
            normalized.startsWith("DELETE FROM main.default.memory_migrations")
          ) {
            migrationUserId = undefined;
            return {
              fetchAll: jest.fn().mockResolvedValue([]),
              close: jest.fn().mockResolvedValue(undefined),
            };
          }

          if (
            normalized.startsWith(
              "INSERT INTO main.default.memory_migrations (user_id)",
            )
          ) {
            const match = normalized.match(/VALUES \('([^']*)'\)/);
            migrationUserId = match ? match[1] : undefined;
            return {
              fetchAll: jest.fn().mockResolvedValue([]),
              close: jest.fn().mockResolvedValue(undefined),
            };
          }

          return {
            fetchAll: jest.fn().mockResolvedValue([]),
            close: jest.fn().mockResolvedValue(undefined),
          };
        });

      const session = {
        executeStatement,
        close: jest.fn().mockResolvedValue(undefined),
      };
      const client = {
        connect: jest.fn().mockResolvedValue(undefined),
        openSession: jest.fn().mockResolvedValue(session),
        close: jest.fn().mockResolvedValue(undefined),
      };

      client.connect.mockResolvedValue(client);

      return {
        DBSQLClient: jest.fn().mockImplementation(() => client),
        __mockClient: client,
        __mockSession: session,
      };
    });

    jest.doMock("axios", () => {
      let endpointExists = false;
      let endpointPendingReadyResponses = 0;
      let indexExists = false;
      let indexPendingReadyResponses = 0;
      let syncPendingReadyResponses = 0;
      let pagedQueryResponses: any[] = [];

      const defaultQueryResponse = {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            ["id-1", JSON.stringify({ user_id: "u1", topic: "alpha" }), 0.98],
            ["id-2", JSON.stringify({ user_id: "u2", topic: "beta" }), 0.75],
          ],
        },
      };

      const httpClient = {
        get: jest.fn().mockImplementation(async (url: string) => {
          if (url === "/endpoints/mem0_vector_search") {
            if (!endpointExists) {
              const error: any = new Error("missing endpoint");
              error.response = { status: 404 };
              throw error;
            }
            if (endpointPendingReadyResponses > 0) {
              endpointPendingReadyResponses -= 1;
              return {
                data: {
                  name: "mem0_vector_search",
                  endpoint_status: { state: "PROVISIONING" },
                },
              };
            }
            return {
              data: {
                name: "mem0_vector_search",
                endpoint_status: { state: "ONLINE" },
              },
            };
          }

          if (url === "/indexes/main.default.memories") {
            if (!indexExists) {
              const error: any = new Error("missing index");
              error.response = { status: 404 };
              throw error;
            }
            if (indexPendingReadyResponses > 0) {
              indexPendingReadyResponses -= 1;
              return {
                data: {
                  name: "main.default.memories",
                  status: { ready: false },
                },
              };
            }
            if (syncPendingReadyResponses > 0) {
              syncPendingReadyResponses -= 1;
              return {
                data: {
                  name: "main.default.memories",
                  status: { ready: false },
                },
              };
            }
            return {
              data: {
                name: "main.default.memories",
                status: { ready: true },
              },
            };
          }

          throw new Error(`Unexpected Databricks GET ${url}`);
        }),
        post: jest.fn().mockImplementation(async (url: string, body: any) => {
          if (url === "/endpoints") {
            endpointExists = true;
            endpointPendingReadyResponses = 1;
            return { data: { endpoint: body.name } };
          }

          if (url === "/indexes") {
            indexExists = true;
            indexPendingReadyResponses = 1;
            return { data: { index: body.name } };
          }

          if (url === "/indexes/main.default.memories/sync") {
            syncPendingReadyResponses = 1;
            return { data: { status: "queued" } };
          }

          if (url === "/indexes/main.default.memories/query") {
            return {
              data:
                pagedQueryResponses.shift() ??
                JSON.parse(JSON.stringify(defaultQueryResponse)),
            };
          }

          if (url === "/indexes/main.default.memories/query-next-page") {
            return {
              data:
                pagedQueryResponses.shift() ??
                JSON.parse(JSON.stringify(defaultQueryResponse)),
            };
          }

          throw new Error(`Unexpected Databricks POST ${url}`);
        }),
        delete: jest.fn().mockImplementation(async (url: string) => {
          if (url === "/indexes/main.default.memories") {
            indexExists = false;
            return { data: {} };
          }
          throw new Error(`Unexpected Databricks DELETE ${url}`);
        }),
      };

      const create = jest.fn().mockReturnValue(httpClient);
      const authPost = jest.fn().mockResolvedValue({
        data: { access_token: "oauth-token", expires_in: 3600 },
      });

      return {
        __esModule: true,
        default: { create, post: authPost },
        create,
        post: authPost,
        __mockHttpClient: httpClient,
        __setPagedQueryResponses: (responses: any[]) => {
          pagedQueryResponses = responses.map((response) =>
            JSON.parse(JSON.stringify(response)),
          );
        },
        __mockAuthPost: authPost,
      };
    });

    DatabricksVectorStore =
      require("../src/vector_stores/databricks").DatabricksVectorStore;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
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
    const databricksSql = require("@databricks/sql");
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    const p3 = store.initialize();
    await Promise.all([p1, p2, p3]);

    const clientInstance = databricksSql.DBSQLClient.mock.results[0].value;
    const session = databricksSql.__mockSession;
    const httpClient = axiosModule.__mockHttpClient;
    expect(clientInstance.connect).toHaveBeenCalledTimes(1);
    expect(clientInstance.openSession).toHaveBeenCalledTimes(1);
    expect(
      httpClient.get.mock.calls.filter(
        ([url]: [string]) => url === "/endpoints/mem0_vector_search",
      ).length,
    ).toBeGreaterThan(1);
    expect(
      httpClient.get.mock.calls.filter(
        ([url]: [string]) => url === "/indexes/main.default.memories",
      ).length,
    ).toBeGreaterThan(1);
    expect(httpClient.post).toHaveBeenCalledWith("/endpoints", {
      name: "mem0_vector_search",
      endpoint_type: "STANDARD",
    });
    expect(httpClient.post).toHaveBeenCalledWith("/indexes", {
      name: "main.default.memories",
      endpoint_name: "mem0_vector_search",
      primary_key: "memory_id",
      index_type: "DELTA_SYNC",
      delta_sync_index_spec: {
        source_table: "main.default.memories",
        pipeline_type: "TRIGGERED",
        columns_to_sync: [
          "memory_id",
          "payload",
          "user_id",
          "agent_id",
          "run_id",
        ],
        embedding_vector_columns: [
          {
            name: "embedding",
            embedding_dimension: 3,
          },
        ],
      },
    });
    expect(
      session.executeStatement.mock.calls.some(
        ([sql]: [string]) =>
          sql.includes("ALTER TABLE main.default.memories") &&
          sql.includes("delta.enableChangeDataFeed"),
      ),
    ).toBe(true);
  });

  it("supports service-principal credentials for REST and SQL setup", async () => {
    const axiosModule = require("axios");
    const databricksSql = require("@databricks/sql");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      clientId: "client-id",
      clientSecret: "client-secret",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    await store.initialize();
    await store.insert([[1, 0, 0]], ["id-1"], [{ user_id: "u1" }]);
    await store.search([1, 0, 0], 1);

    expect(axiosModule.__mockAuthPost).toHaveBeenCalledWith(
      "https://workspace.databricks.com/oidc/v1/token",
      expect.any(URLSearchParams),
      expect.objectContaining({
        auth: {
          username: "client-id",
          password: "client-secret",
        },
      }),
    );
    const authDetails = axiosModule.__mockAuthPost.mock.calls.map(
      ([, params]: [string, URLSearchParams]) =>
        params.get("authorization_details"),
    );
    const readDetails = JSON.stringify([
      {
        type: "unity_catalog_permission",
        securable_type: "table",
        securable_object_name: "main.default.memories",
        operation: "ReadVectorIndex",
      },
    ]);
    const writeDetails = JSON.stringify([
      {
        type: "unity_catalog_permission",
        securable_type: "table",
        securable_object_name: "main.default.memories",
        operation: "WriteVectorIndex",
      },
    ]);

    expect(authDetails).toContain(null);
    expect(authDetails).toContain(readDetails);
    expect(authDetails).toContain(writeDetails);
    expect(databricksSql.__mockClient.connect).toHaveBeenCalledWith(
      expect.objectContaining({
        authType: "databricks-oauth",
        oauthClientId: "client-id",
        oauthClientSecret: "client-secret",
      }),
    );
  });

  it("shapes Databricks SQL writes, syncs triggered indexes, and normalizes search results", async () => {
    const databricksSql = require("@databricks/sql");
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
    });

    await store.initialize();
    await store.insert(
      [[1, 0, 0]],
      ["id-1"],
      [{ user_id: "u1", topic: "alpha" }],
    );

    const session = databricksSql.__mockSession;
    expect(session.executeStatement).toHaveBeenCalledWith(
      expect.stringContaining("INSERT INTO main.default.memories"),
    );
    expect(session.executeStatement).toHaveBeenCalledWith(
      expect.stringContaining("'id-1'"),
    );
    expect(session.executeStatement).toHaveBeenCalledWith(
      expect.stringContaining("array(1, 0, 0)"),
    );
    await store.update("id-1", [0, 1, 0], { user_id: "u1", topic: "beta" });
    await store.delete("id-1");

    const results = await store.search([1, 0, 0], 5, {
      user_id: "u1",
      topic: "alpha",
    });
    const httpClient = axiosModule.__mockHttpClient;
    expect(
      httpClient.post.mock.calls.filter(
        ([url]: [string]) => url === "/indexes/main.default.memories/sync",
      ),
    ).toHaveLength(3);
    expect(
      httpClient.get.mock.calls.filter(
        ([url]: [string]) => url === "/indexes/main.default.memories",
      ).length,
    ).toBeGreaterThan(4);
    expect(httpClient.post).toHaveBeenCalledWith(
      "/indexes/main.default.memories/query",
      expect.objectContaining({
        columns: ["memory_id", "payload"],
        filters_json: JSON.stringify({ user_id: "u1" }),
        query_type: "ANN",
        query_vector: [1, 0, 0],
      }),
    );
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("keeps metadata-only filters local for standard endpoints", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.search([1, 0, 0], 5, { topic: "alpha" });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        columns: ["memory_id", "payload"],
        query_type: "ANN",
        query_vector: [1, 0, 0],
      }),
    );
    expect(queryCall?.[1]).not.toHaveProperty("filters_json");
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("applies multiple local metadata operators on the same field", async () => {
    const axiosModule = require("axios");
    axiosModule.__setPagedQueryResponses([
      {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            [
              "id-1",
              JSON.stringify({ user_id: "u1", importance: 1.0, topic: "high" }),
              0.99,
            ],
            [
              "id-2",
              JSON.stringify({
                user_id: "u1",
                importance: 0.75,
                topic: "within-range",
              }),
              0.98,
            ],
          ],
        },
      },
    ]);

    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.search([1, 0, 0], 5, {
      importance: { gte: 0.5, lte: 0.9 },
    });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).not.toHaveProperty("filters_json");
    expect(results).toEqual([
      {
        id: "id-2",
        payload: { user_id: "u1", importance: 0.75, topic: "within-range" },
        score: 0.98,
      },
    ]);
  });

  it("paginates when local-only filters need matches beyond the first page", async () => {
    const axiosModule = require("axios");
    axiosModule.__setPagedQueryResponses([
      {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            ["id-2", JSON.stringify({ user_id: "u2", topic: "beta" }), 0.99],
          ],
          next_page_token: "page-2",
        },
      },
      {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            ["id-1", JSON.stringify({ user_id: "u1", topic: "alpha" }), 0.98],
          ],
        },
      },
    ]);

    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.search([1, 0, 0], 1, { topic: "alpha" });
    expect(
      axiosModule.__mockHttpClient.post.mock.calls.some(
        ([url]: [string]) =>
          url === "/indexes/main.default.memories/query-next-page",
      ),
    ).toBe(true);
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("paginates across Databricks result pages when topK exceeds the first page", async () => {
    const axiosModule = require("axios");
    axiosModule.__setPagedQueryResponses([
      {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            ["id-1", JSON.stringify({ user_id: "u1", topic: "alpha" }), 0.99],
          ],
          next_page_token: "page-2",
        },
      },
      {
        result: {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "payload" }],
          },
          data_array: [
            ["id-2", JSON.stringify({ user_id: "u2", topic: "beta" }), 0.98],
          ],
        },
      },
    ]);

    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.search([1, 0, 0], 1001);
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        num_results: 1001,
      }),
    );
    expect(
      axiosModule.__mockHttpClient.post.mock.calls.some(
        ([url]: [string]) =>
          url === "/indexes/main.default.memories/query-next-page",
      ),
    ).toBe(true);
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.99,
      },
      {
        id: "id-2",
        payload: { user_id: "u2", topic: "beta" },
        score: 0.98,
      },
    ]);
  });

  it("caps full-text local-fallback requests at Databricks' 200-result limit", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.keywordSearch("alpha", 5, { topic: "alpha" });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        num_results: 200,
        query_type: "FULL_TEXT",
        query_text: "alpha",
      }),
    );
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("uses SQL-like filters for storage-optimized endpoints", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 16,
      endpointType: "STORAGE_OPTIMIZED",
    });
    const query = new Array(16).fill(0);
    query[0] = 1;

    const results = await store.search(query, 5, {
      user_id: "u1",
      topic: "alpha",
    });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        columns: ["memory_id", "payload"],
        filters: "user_id = 'u1'",
        query_type: "ANN",
        query_vector: query,
      }),
    );
    expect(queryCall?.[1]).not.toHaveProperty("filters_json");
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("translates storage-optimized array shorthand filters into IN clauses", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 16,
      endpointType: "STORAGE_OPTIMIZED",
    });
    const query = new Array(16).fill(0);
    query[0] = 1;

    await store.search(query, 5, {
      user_id: ["u1", "u2"],
    });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        filters: "user_id IN ('u1', 'u2')",
      }),
    );
    expect(queryCall?.[1]).not.toHaveProperty("filters_json");
  });

  it("falls back to local filtering for logical operators", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const orResults = await store.search([1, 0, 0], 5, {
      $or: [{ user_id: "u1" }, { topic: "beta" }],
    });
    const notResults = await store.search([1, 0, 0], 5, {
      $not: [{ user_id: "u2" }],
    });
    const queryCalls = axiosModule.__mockHttpClient.post.mock.calls.filter(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCalls).toHaveLength(2);
    expect(queryCalls[0][1]).not.toHaveProperty("filters_json");
    expect(queryCalls[1][1]).not.toHaveProperty("filters_json");
    expect(orResults.map((result: any) => result.id)).toEqual(["id-1", "id-2"]);
    expect(notResults.map((result: any) => result.id)).toEqual(["id-1"]);
  });

  it("keeps memory_id filters aligned between Databricks and local fallback", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      syncPollIntervalMs: 0,
    });

    const results = await store.search([1, 0, 0], 5, { memory_id: "id-1" });
    const queryCall = axiosModule.__mockHttpClient.post.mock.calls.find(
      ([url]: [string]) => url === "/indexes/main.default.memories/query",
    );

    expect(queryCall?.[1]).toEqual(
      expect.objectContaining({
        filters_json: JSON.stringify({ memory_id: "id-1" }),
      }),
    );
    expect(results).toEqual([
      {
        id: "id-1",
        payload: { user_id: "u1", topic: "alpha" },
        score: 0.98,
      },
    ]);
  });

  it("omits columns_to_sync for storage-optimized endpoints", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 16,
      endpointType: "STORAGE_OPTIMIZED",
    });

    await store.initialize();

    expect(axiosModule.__mockHttpClient.post).toHaveBeenCalledWith("/indexes", {
      name: "main.default.memories",
      endpoint_name: "mem0_vector_search",
      primary_key: "memory_id",
      index_type: "DELTA_SYNC",
      delta_sync_index_spec: {
        source_table: "main.default.memories",
        pipeline_type: "TRIGGERED",
        columns_to_sync: undefined,
        embedding_vector_columns: [
          {
            name: "embedding",
            embedding_dimension: 16,
          },
        ],
      },
    });
  });

  it("rejects invalid storage-optimized embedding dimensions", () => {
    expect(
      () =>
        new DatabricksVectorStore({
          workspaceUrl: "https://workspace.databricks.com",
          httpPath: "/sql/1.0/warehouses/test",
          accessToken: "dapi-test",
          catalog: "main",
          schema: "default",
          collectionName: "memories",
          dimension: 3,
          endpointType: "STORAGE_OPTIMIZED",
        }),
    ).toThrow("require dimensions divisible by 16");
  });

  it("rejects HYBRID vector search without query text", async () => {
    const axiosModule = require("axios");
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
      queryType: "HYBRID",
      syncPollIntervalMs: 0,
    });

    await expect(store.search([1, 0, 0], 5)).rejects.toThrow(
      "Databricks HYBRID search requires query_text",
    );
    expect(
      axiosModule.__mockHttpClient.post.mock.calls.find(
        ([url]: [string]) => url === "/indexes/main.default.memories/query",
      ),
    ).toBeUndefined();
  });

  it("roundtrips migration user ids", async () => {
    const store = new DatabricksVectorStore({
      workspaceUrl: "https://workspace.databricks.com",
      httpPath: "/sql/1.0/warehouses/test",
      accessToken: "dapi-test",
      catalog: "main",
      schema: "default",
      collectionName: "memories",
      dimension: 3,
    });

    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");
  });
});

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
// 8. LangchainVectorStore — mock Langchain client, verify no-op init
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

  it("derives a separate Databricks entity table when provider casing differs", async () => {
    const primaryStore = createMockVectorStore();
    const entityStore = createMockVectorStore();
    mockVectorStoreFactory.create
      .mockReturnValueOnce(primaryStore)
      .mockReturnValueOnce(entityStore);

    const mem = new MemoryClass({
      embedder: { provider: "openai", config: { apiKey: "k" } },
      vectorStore: {
        provider: "Databricks",
        config: {
          workspaceUrl: "https://workspace.databricks.com",
          httpPath: "/sql/1.0/warehouses/test",
          accessToken: "dapi-test",
          collectionName: "memories",
          tableName: "memory_rows",
          dimension: 1536,
        },
      },
      llm: { provider: "openai", config: { apiKey: "k" } },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });
    await (mem as any).getEntityStore();

    expect(mockVectorStoreFactory.create).toHaveBeenNthCalledWith(
      2,
      "databricks",
      expect.objectContaining({
        collectionName: "memories_entities",
        tableName: "memory_rows_entities",
      }),
    );
    expect(entityStore.initialize).toHaveBeenCalled();
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
