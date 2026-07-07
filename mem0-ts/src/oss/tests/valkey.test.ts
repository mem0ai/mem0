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

    // Read back through the real stateful mock store (populated by the hset
    // above) rather than a hand-rolled hgetall override, so the insert→get
    // round-trip and timestamp rendering are genuinely exercised.
    const result = await store.get("mem-1");
    expect(result?.id).toBe("mem-1");
    expect(result?.payload.data).toBe("hello valkey");
    expect(result?.payload.userId).toBe("alice");
    // created_at is persisted as unix seconds and rendered back to its ISO instant.
    expect(result?.payload.createdAt).toBe("2024-01-01T00:00:00.000Z");
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

  it("passes URL credentials to Cluster via redisOptions in cluster mode", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://user:s3cret@cluster.example:6379",
      clusterMode: true,
    });
    await store.initialize();

    const iovalkey = require("iovalkey");
    // Cluster ignores URL-embedded auth, so credentials must be forwarded
    // explicitly via redisOptions — otherwise every cluster connection is
    // silently unauthenticated.
    expect(iovalkey.Cluster).toHaveBeenCalledWith(
      [{ host: "cluster.example", port: 6379 }],
      { redisOptions: { username: "user", password: "s3cret" } },
    );
  });

  it("renders timestamps in the configured timezone", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
      timezone: "America/New_York",
    });
    await store.initialize();

    await store.insert(
      [[0.1, 0.2, 0.3, 0.4]],
      ["mem-tz"],
      [{ data: "tz", created_at: "2024-01-01T00:00:00.000Z" }],
    );

    const result = await store.get("mem-tz");
    // 2024-01-01T00:00:00Z is 2023-12-31T19:00:00 in America/New_York (UTC-5).
    expect(result?.payload.createdAt).toBe("2023-12-31T19:00:00-05:00");
  });

  it("escapes special characters in filter values (query-injection safety)", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();

    const iovalkey = require("iovalkey");
    const mockClient = iovalkey.__mockClient;
    await store.search([0.1, 0.2, 0.3, 0.4], 5, { user_id: "a|b c" });

    const searchCall = mockClient.call.mock.calls.find(
      (call: any[]) => call[0] === "FT.SEARCH",
    );
    expect(searchCall).toBeDefined();
    // `|` and whitespace must be escaped so a filter value can't rewrite the query.
    expect(searchCall[2]).toContain("@user_id:{a\\|b\\ c}");
  });

  it("does not raise an unhandled rejection when initialization fails", async () => {
    const iovalkey = require("iovalkey");
    iovalkey.__mockClient.call.mockImplementationOnce(async () => {
      throw new Error("ERR unknown command 'FT._LIST'");
    });
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const unhandled: unknown[] = [];
    const onUnhandled = (reason: unknown) => unhandled.push(reason);
    process.on("unhandledRejection", onUnhandled);

    // The constructor kicks off initialize() in a detached .catch; it must log
    // and swallow, never re-throw — a re-throw surfaces as an unhandled promise
    // rejection that can crash the Node process.
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });

    await expect(store.initialize()).rejects.toThrow(/search module/i);

    // Give Node a macrotask to surface any unhandled rejection from the catch.
    await new Promise((resolve) => setTimeout(resolve, 10));
    process.off("unhandledRejection", onUnhandled);

    expect(unhandled).toHaveLength(0);
    expect(errorSpy).toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
