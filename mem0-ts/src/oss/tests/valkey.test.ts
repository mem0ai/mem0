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
    expect(result?.payload.user_id).toBe("alice");
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

  // --- GH-6266: Payload shape normalization tests ---

  describe("GH-6266: docToResult payload normalization", () => {
    it("preserves entity IDs in snake_case (user_id, agent_id, run_id)", async () => {
      const store = new ValkeyDB({
        collectionName: "test",
        embeddingModelDims: 4,
        valkeyUrl: "valkey://localhost:6379",
      });
      await store.initialize();

      await store.insert(
        [[0.1, 0.2, 0.3, 0.4]],
        ["mem-aea588"],
        [
          {
            data: "entity id test",
            hash: "h1",
            created_at: "2024-06-01T00:00:00.000Z",
            user_id: "u1",
            agent_id: "a1",
            run_id: "r1",
          },
        ],
      );

      const result = await store.get("mem-aea588");
      expect(result).not.toBeNull();
      // Entity IDs MUST be snake_case
      expect(result?.payload.user_id).toBe("u1");
      expect(result?.payload.agent_id).toBe("a1");
      expect(result?.payload.run_id).toBe("r1");
      // camelCase variants MUST NOT exist
      expect(result?.payload.userId).toBeUndefined();
      expect(result?.payload.agentId).toBeUndefined();
      expect(result?.payload.runId).toBeUndefined();
    });

    it("does not leak entity IDs into metadata", async () => {
      const store = new ValkeyDB({
        collectionName: "test",
        embeddingModelDims: 4,
        valkeyUrl: "valkey://localhost:6379",
      });
      await store.initialize();

      await store.insert(
        [[0.1, 0.2, 0.3, 0.4]],
        ["mem-leak"],
        [
          {
            data: "leak test",
            hash: "h2",
            created_at: "2024-06-01T00:00:00.000Z",
            user_id: "u2",
            agent_id: "a2",
            run_id: "r2",
            metadata: JSON.stringify({ custom_key: "custom_value" }),
          },
        ],
      );

      const result = await store.get("mem-leak");
      expect(result).not.toBeNull();
      // Entity IDs must NOT appear inside metadata spillover
      const payloadKeys = Object.keys(result!.payload);
      // The payload should have user_id at top level, not userId
      expect(payloadKeys).toContain("user_id");
      expect(payloadKeys).not.toContain("userId");
      expect(payloadKeys).toContain("agent_id");
      expect(payloadKeys).not.toContain("agentId");
    });

    it("renders timestamps in camelCase (createdAt, updatedAt)", async () => {
      const store = new ValkeyDB({
        collectionName: "test",
        embeddingModelDims: 4,
        valkeyUrl: "valkey://localhost:6379",
      });
      await store.initialize();

      await store.insert(
        [[0.1, 0.2, 0.3, 0.4]],
        ["mem-ts"],
        [
          {
            data: "timestamp test",
            hash: "h3",
            created_at: "2024-06-01T12:00:00.000Z",
            user_id: "u3",
          },
        ],
      );

      // Set updated_at via update() since insert() doesn't store it
      await store.update("mem-ts", [0.1, 0.2, 0.3, 0.4], {
        data: "timestamp test",
        hash: "h3",
        created_at: "2024-06-01T12:00:00.000Z",
        updated_at: "2024-06-02T12:00:00.000Z",
        user_id: "u3",
      });

      const result = await store.get("mem-ts");
      expect(result).not.toBeNull();
      // Timestamps MUST be camelCase
      expect(result?.payload.createdAt).toBeDefined();
      expect(result?.payload.updatedAt).toBeDefined();
      // snake_case timestamp keys MUST NOT exist
      expect(result?.payload.created_at).toBeUndefined();
      expect(result?.payload.updated_at).toBeUndefined();
    });

    it("camelCases arbitrary metadata keys", async () => {
      const store = new ValkeyDB({
        collectionName: "test",
        embeddingModelDims: 4,
        valkeyUrl: "valkey://localhost:6379",
      });
      await store.initialize();

      // Custom fields passed at top level end up in the metadata JSON blob
      // after EXCLUDED_KEYS are filtered out during insert.
      await store.insert(
        [[0.1, 0.2, 0.3, 0.4]],
        ["mem-meta"],
        [
          {
            data: "metadata test",
            hash: "h4",
            created_at: "2024-06-01T00:00:00.000Z",
            user_id: "u4",
            some_custom_field: "value1",
            another_key: "value2",
          },
        ],
      );

      const result = await store.get("mem-meta");
      expect(result).not.toBeNull();
      // Metadata keys should be camelCased
      expect(result?.payload.someCustomField).toBe("value1");
      expect(result?.payload.anotherKey).toBe("value2");
      // Original snake_case metadata keys should NOT exist
      expect(result?.payload.some_custom_field).toBeUndefined();
      expect(result?.payload.another_key).toBeUndefined();
    });
  });
});
