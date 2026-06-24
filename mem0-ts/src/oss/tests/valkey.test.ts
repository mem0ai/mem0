/**
 * Valkey vector store unit tests with mocked iovalkey client.
 */
/// <reference types="jest" />

describe("Valkey – mocked iovalkey client", () => {
  let ValkeyDB: any;

  beforeEach(() => {
    jest.resetModules();

    jest.doMock("iovalkey", () => {
      const store = new Map<string, Record<string, string>>();
      const mockClient = {
        on: jest.fn(),
        call: jest.fn().mockImplementation(async (...args: any[]) => {
          const command = args[0];
          if (command === "FT._LIST") {
            return [];
          }
          if (command === "FT.INFO") {
            throw new Error("Unknown index name");
          }
          if (command === "FT.CREATE") {
            return "OK";
          }
          if (command === "FT.SEARCH") {
            return [0];
          }
          if (command === "FT.DROPINDEX") {
            return "OK";
          }
          return "OK";
        }),
        hset: jest.fn().mockImplementation(async (key: string, obj: any) => {
          const existing = store.get(key) ?? {};
          const normalized: Record<string, string> = { ...existing };
          for (const [field, value] of Object.entries(obj)) {
            normalized[field] =
              value instanceof Buffer ? value.toString("hex") : String(value);
          }
          store.set(key, normalized);
          return 1;
        }),
        hgetall: jest.fn().mockImplementation(async (key: string) => {
          return store.get(key) ?? {};
        }),
        exists: jest.fn().mockImplementation(async (key: string) => {
          return store.has(key) ? 1 : 0;
        }),
        del: jest.fn().mockImplementation(async (key: string) => {
          store.delete(key);
          return 1;
        }),
        get: jest.fn().mockResolvedValue(null),
        set: jest.fn().mockResolvedValue("OK"),
        quit: jest.fn().mockResolvedValue("OK"),
      };

      const Valkey = jest.fn().mockImplementation(() => mockClient);
      const Cluster = jest.fn().mockImplementation(() => mockClient);

      return {
        __esModule: true,
        default: Valkey,
        Cluster,
        __mockClient: mockClient,
      };
    });

    ValkeyDB = require("../src/vector_stores/valkey").ValkeyDB;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("implements full VectorStore interface", () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
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
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });

    const p1 = store.initialize();
    const p2 = store.initialize();
    await Promise.all([p1, p2]);

    const iovalkey = require("iovalkey");
    expect(iovalkey.default).toHaveBeenCalledTimes(1);
  });

  it("creates HNSW index when indexType is hnsw", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
      indexType: "hnsw",
    });
    await store.initialize();

    const iovalkey = require("iovalkey");
    const mockClient = iovalkey.__mockClient;
    const createCall = mockClient.call.mock.calls.find(
      (call: any[]) => call[0] === "FT.CREATE",
    );
    expect(createCall).toBeDefined();
    expect(createCall).toContain("HNSW");
  });

  it("inserts and retrieves a vector", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();

    await store.insert(
      [[0.1, 0.2, 0.3, 0.4]],
      ["mem-1"],
      [
        {
          data: "hello valkey",
          hash: "hash-1",
          created_at: "2024-01-01T00:00:00.000Z",
          user_id: "alice",
        },
      ],
    );

    const iovalkey = require("iovalkey");
    const mockClient = iovalkey.__mockClient;
    expect(mockClient.hset).toHaveBeenCalledWith(
      "mem0:test:mem-1",
      expect.objectContaining({
        memory_id: "mem-1",
        memory: "hello valkey",
        hash: "hash-1",
        user_id: "alice",
      }),
    );

    mockClient.hgetall.mockResolvedValueOnce({
      memory_id: "mem-1",
      hash: "hash-1",
      memory: "hello valkey",
      created_at: "1704067200",
      user_id: "alice",
      metadata: "{}",
    });

    const result = await store.get("mem-1");
    expect(result?.id).toBe("mem-1");
    expect(result?.payload.data).toBe("hello valkey");
  });

  it("uses Cluster client when clusterMode is enabled", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://cluster.example:6379",
      clusterMode: true,
    });
    await store.initialize();

    const iovalkey = require("iovalkey");
    expect(iovalkey.Cluster).toHaveBeenCalledTimes(1);
    expect(iovalkey.default).not.toHaveBeenCalled();
  });
});
