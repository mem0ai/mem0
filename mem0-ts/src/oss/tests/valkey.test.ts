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
          if (command === "EVAL") {
            // Mirrors HSET_IF_EXISTS in valkey.ts: write only when the hash exists.
            const [, , , key, ...pairs] = args;
            const existing = store.get(key);
            if (!existing) return 0;
            for (let i = 0; i < pairs.length; i += 2) {
              const value = pairs[i + 1];
              existing[pairs[i]] =
                value instanceof Buffer ? value.toString("hex") : String(value);
            }
            return 1;
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

  it("update never recreates a deleted memory and only patches existing ones", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();
    const mockClient = require("iovalkey").__mockClient;
    const hex = (v: number[]) =>
      Buffer.from(new Float32Array(v).buffer).toString("hex");

    await store.insert(
      [
        [0.1, 0.2, 0.3, 0.4],
        [0.1, 0.2, 0.3, 0.4],
      ],
      ["mem-u", "mem-gone"],
      [{ data: "old", user_id: "alice" }, { data: "doomed" }],
    );
    await store.delete("mem-gone");
    mockClient.hset.mockClear();

    await expect(
      store.update("mem-gone", [0.5, 0.6, 0.7, 0.8], { data: "x" }),
    ).resolves.toBe(false);
    await expect(store.get("mem-gone")).resolves.toBeNull();

    await expect(
      store.update("mem-u", [0.5, 0.6, 0.7, 0.8], { data: "new" }),
    ).resolves.toBe(true);
    // Payload-only: the embedding written above must survive.
    await expect(
      store.update("mem-u", null as any, { data: "newer" }),
    ).resolves.toBe(true);

    const row = await mockClient.hgetall("mem0:test:mem-u");
    expect(row.memory).toBe("newer");
    expect(row.user_id).toBe("alice");
    expect(row.embedding).toBe(hex([0.5, 0.6, 0.7, 0.8]));
    expect(mockClient.hset).not.toHaveBeenCalled();
  });

  it("NOPERM falls back to WATCH/MULTI on a duplicate connection and retries", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();
    const mockClient = require("iovalkey").__mockClient;
    const noperm = new Error(
      "NOPERM User u has no permissions to run the 'eval' command",
    );
    mockClient.call
      .mockRejectedValueOnce(noperm)
      .mockRejectedValueOnce(noperm)
      .mockRejectedValueOnce(new Error("ERR boom"));
    // iovalkey resolves exec() to null when a watched key changed: retry.
    const exec = jest
      .fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValue([[null, 1]]);
    const hset = jest.fn(() => ({ exec }));
    const conn = {
      watch: jest.fn(),
      unwatch: jest.fn(),
      disconnect: jest.fn(),
      exists: jest.fn().mockResolvedValueOnce(0).mockResolvedValue(1),
      multi: jest.fn(() => ({ hset })),
    };
    mockClient.duplicate = jest.fn(() => conn);
    const vector = [0.1, 0.2, 0.3, 0.4];

    await expect(store.update("gone", vector, { data: "x" })).resolves.toBe(
      false,
    );
    expect(conn.unwatch).toHaveBeenCalledTimes(1);
    expect(hset).not.toHaveBeenCalled();

    await expect(store.update("mem-a", vector, { data: "new" })).resolves.toBe(
      true,
    );
    expect(conn.watch).toHaveBeenCalledTimes(3);
    expect(hset).toHaveBeenCalledTimes(2);
    expect(hset).toHaveBeenLastCalledWith(
      "mem0:test:mem-a",
      expect.objectContaining({ memory_id: "mem-a", memory: "new" }),
    );
    expect(conn.disconnect).toHaveBeenCalledTimes(2);

    await expect(store.update("mem-a", vector, {})).rejects.toThrow("ERR boom");
    expect(mockClient.hset).not.toHaveBeenCalled();
  });

  it("NOPERM fallback rethrows a command error inside EXEC instead of reporting success", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();
    const mockClient = require("iovalkey").__mockClient;
    mockClient.call.mockRejectedValueOnce(
      new Error("NOPERM User u has no permissions to run the 'eval' command"),
    );
    const wrongType = new Error("WRONGTYPE Operation against a key");
    const { wrapMultiResult } = jest.requireActual("iovalkey/built/utils");
    const conn = {
      watch: jest.fn(),
      unwatch: jest.fn(),
      disconnect: jest.fn(),
      exists: jest.fn().mockResolvedValue(1),
      multi: () => ({
        hset: () => ({ exec: async () => wrapMultiResult([wrongType]) }),
      }),
    };
    mockClient.duplicate = jest.fn(() => conn);

    await expect(
      store.update("mem-a", [0.1, 0.2, 0.3, 0.4], { data: "x" }),
    ).rejects.toBe(wrongType);
    expect(conn.disconnect).toHaveBeenCalledTimes(1);
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

  it("get returns entity ids as snake_case", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();

    await store.insert(
      [[0.1, 0.2, 0.3, 0.4]],
      ["mem-ids"],
      [
        {
          data: "likes tea",
          user_id: "user-1",
          agent_id: "agent-1",
          run_id: "run-1",
        },
      ],
    );

    const result = await store.get("mem-ids");
    expect(result?.payload.user_id).toBe("user-1");
    expect(result?.payload.agent_id).toBe("agent-1");
    expect(result?.payload.run_id).toBe("run-1");
    expect(result?.payload).not.toHaveProperty("userId");
    expect(result?.payload).not.toHaveProperty("agentId");
    expect(result?.payload).not.toHaveProperty("runId");
  });

  it("search and list return entity ids as snake_case", async () => {
    const store = new ValkeyDB({
      collectionName: "test",
      embeddingModelDims: 4,
      valkeyUrl: "valkey://localhost:6379",
    });
    await store.initialize();

    const iovalkey = require("iovalkey");
    const mockClient = iovalkey.__mockClient;
    mockClient.call.mockImplementation(async (...args: any[]) => {
      if (args[0] === "FT.SEARCH") {
        return [
          1,
          "mem0:test:mem-search",
          [
            "memory_id",
            "mem-search",
            "hash",
            "h1",
            "memory",
            "likes tea",
            "created_at",
            "1700000000",
            "agent_id",
            "agent-1",
            "run_id",
            "run-1",
            "user_id",
            "user-1",
            "metadata",
            "{}",
            "vector_score",
            "0.1",
          ],
        ];
      }
      return "OK";
    });

    const results = await store.search([0.1, 0.2, 0.3, 0.4], 5);
    expect(results[0].payload.user_id).toBe("user-1");
    expect(results[0].payload.agent_id).toBe("agent-1");
    expect(results[0].payload.run_id).toBe("run-1");
    expect(results[0].payload).not.toHaveProperty("userId");
    expect(results[0].payload).not.toHaveProperty("agentId");
    expect(results[0].payload).not.toHaveProperty("runId");

    const [listed] = await store.list();
    expect(listed[0].payload.user_id).toBe("user-1");
    expect(listed[0].payload.agent_id).toBe("agent-1");
    expect(listed[0].payload.run_id).toBe("run-1");
    expect(listed[0].payload).not.toHaveProperty("userId");
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
