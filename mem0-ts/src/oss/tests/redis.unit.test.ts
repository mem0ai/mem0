import { RedisDB } from "../src/vector_stores/redis";

jest.mock("redis", () => ({
  WatchError: class WatchError extends Error {},
  createClient: jest.fn(() => ({
    connect: jest.fn(),
    on: jest.fn(),
    moduleList: jest.fn().mockResolvedValue([{ name: "search", ver: 20800 }]),
    ft: {
      create: jest.fn(),
      search: jest.fn(),
      info: jest.fn().mockRejectedValue(new Error("Unknown index")),
      _list: jest.fn().mockResolvedValue([]),
    },
    hSet: jest.fn(),
    sendCommand: jest.fn().mockResolvedValue(1),
    executeIsolated: jest.fn(),
    hGetAll: jest.fn(),
    del: jest.fn(),
    exists: jest.fn(),
    quit: jest.fn(),
  })),
}));

// update() sends EVAL <script> 1 <key> field value ...; rebuild the field map.
function evalFields(args: any[]): Record<string, any> {
  const fields: Record<string, any> = {};
  for (let i = 4; i < args.length; i += 2) fields[args[i]] = args[i + 1];
  return fields;
}

function createStore(): RedisDB {
  return new RedisDB({
    redisUrl: "redis://localhost:6379",
    collectionName: "test",
    embeddingModelDims: 4,
  });
}

describe("RedisDB – entity payload handling", () => {
  let store: RedisDB;
  let mockClient: any;

  beforeAll(async () => {
    store = createStore();
    await store.initialize();
    mockClient = (store as any).client;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("insert with entity payload (no hash/created_at) does not produce NaN", async () => {
    const entityPayload = {
      data: "OpenAI",
      entityType: "organization",
      linkedMemoryIds: ["mem-1"],
      userId: "test_user",
    };

    await store.insert([[0.1, 0.2, 0.3, 0.4]], ["entity-1"], [entityPayload]);

    expect(mockClient.hSet).toHaveBeenCalledTimes(1);
    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.memory_id).toBe("entity-1");
    expect(entry.memory).toBe("OpenAI");
    expect(entry.hash).toBe("");
    expect(entry.created_at).toBe(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
  });

  test("update with entity payload (no hash/created_at/updated_at) does not produce NaN", async () => {
    const entityPayload = {
      data: "OpenAI",
      entityType: "organization",
      linkedMemoryIds: ["mem-1"],
      userId: "test_user",
    };

    await store.update("entity-1", [0.1, 0.2, 0.3, 0.4], entityPayload);

    expect(mockClient.sendCommand).toHaveBeenCalledTimes(1);
    const entry = evalFields(mockClient.sendCommand.mock.calls[0][0]);

    expect(entry.memory_id).toBe("entity-1");
    expect(entry.memory).toBe("OpenAI");
    expect(entry.hash).toBe("");
    expect(entry.created_at).toBe("0");
    expect(entry.updated_at).toBe("0");
  });

  test("update with normal payload preserves timestamps", async () => {
    const normalPayload = {
      data: "likes coffee",
      hash: "abc123",
      createdAt: "2026-06-25T10:00:00.000Z",
      updatedAt: "2026-06-25T12:00:00.000Z",
      userId: "test_user",
    };

    await store.update("mem-1", [0.1, 0.2, 0.3, 0.4], normalPayload);

    const entry = evalFields(mockClient.sendCommand.mock.calls[0][0]);

    expect(entry.hash).toBe("abc123");
    expect(entry.memory).toBe("likes coffee");
    expect(entry.created_at).toBe(String(Date.parse(normalPayload.createdAt)));
    expect(entry.updated_at).toBe(String(Date.parse(normalPayload.updatedAt)));
  });

  test("update on a missing id returns false and never calls HSET directly", async () => {
    mockClient.sendCommand.mockResolvedValueOnce(0);

    await expect(
      store.update("gone", [0.1, 0.2, 0.3, 0.4], { data: "x" }),
    ).resolves.toBe(false);

    expect(mockClient.hSet).not.toHaveBeenCalled();
    const args = mockClient.sendCommand.mock.calls[0][0];
    expect(args.slice(0, 4)).toEqual([
      "EVAL",
      expect.stringContaining("EXISTS"),
      "1",
      "mem0:test:gone",
    ]);
  });

  test("update on an existing id returns true and sends the same hash fields", async () => {
    mockClient.sendCommand.mockResolvedValueOnce(1);

    await expect(
      store.update("mem-1", [0.1, 0.2, 0.3, 0.4], {
        data: "tea",
        userId: "u1",
      }),
    ).resolves.toBe(true);

    expect(evalFields(mockClient.sendCommand.mock.calls[0][0])).toEqual({
      memory_id: "mem-1",
      hash: "",
      memory: "tea",
      created_at: "0",
      updated_at: "0",
      embedding: Buffer.from(new Float32Array([0.1, 0.2, 0.3, 0.4]).buffer),
      user_id: "u1",
      metadata: "{}",
    });
  });

  test("NOPERM falls back to WATCH/MULTI on an isolated connection and retries", async () => {
    const { WatchError } = jest.requireMock("redis");
    const noperm = new Error(
      "NOPERM User u has no permissions to run the 'eval' command",
    );
    mockClient.sendCommand
      .mockRejectedValueOnce(noperm)
      .mockRejectedValueOnce(noperm)
      .mockRejectedValueOnce(new Error("ERR boom"));
    // The first EXEC is aborted because a watched key changed under us.
    const exec = jest
      .fn()
      .mockRejectedValueOnce(new WatchError())
      .mockResolvedValue([1]);
    const hSet = jest.fn(() => ({ exec }));
    const conn = {
      watch: jest.fn(),
      unwatch: jest.fn(),
      exists: jest.fn().mockResolvedValueOnce(0).mockResolvedValue(1),
      multi: jest.fn(() => ({ hSet })),
    };
    mockClient.executeIsolated.mockImplementation((fn: any) => fn(conn));
    const vector = [0.1, 0.2, 0.3, 0.4];

    await expect(store.update("gone", vector, { data: "x" })).resolves.toBe(
      false,
    );
    expect(conn.unwatch).toHaveBeenCalledTimes(1);
    expect(hSet).not.toHaveBeenCalled();

    await expect(store.update("mem-1", vector, { data: "tea" })).resolves.toBe(
      true,
    );
    expect(conn.watch).toHaveBeenCalledTimes(3);
    expect(hSet).toHaveBeenCalledTimes(2);
    expect(hSet).toHaveBeenLastCalledWith(
      "mem0:test:mem-1",
      expect.objectContaining({ memory_id: "mem-1", memory: "tea" }),
    );

    await expect(store.update("mem-1", vector, {})).rejects.toThrow("ERR boom");
    expect(mockClient.hSet).not.toHaveBeenCalled();
  });

  test("payload-only update leaves the stored embedding alone", async () => {
    mockClient.sendCommand.mockResolvedValueOnce(1);

    await expect(
      store.update("mem-1", null as any, { data: "x" }),
    ).resolves.toBe(true);

    expect(
      evalFields(mockClient.sendCommand.mock.calls[0][0]),
    ).not.toHaveProperty("embedding");
  });

  test("insert with normal payload preserves timestamp", async () => {
    const normalPayload = {
      data: "likes coffee",
      hash: "abc123",
      createdAt: "2026-06-25T10:00:00.000Z",
      userId: "test_user",
    };

    await store.insert([[0.1, 0.2, 0.3, 0.4]], ["mem-1"], [normalPayload]);

    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.hash).toBe("abc123");
    expect(entry.memory).toBe("likes coffee");
    expect(entry.created_at).toBeGreaterThan(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
  });

  test("search returns entity ids as snake_case", async () => {
    mockClient.ft.search.mockResolvedValue({
      total: 1,
      documents: [
        {
          id: "mem0:test:mem-1",
          value: {
            memory_id: "mem-1",
            hash: "h1",
            memory: "likes coffee",
            created_at: "1700000000000",
            agent_id: "agent-1",
            run_id: "run-1",
            user_id: "user-1",
            metadata: "{}",
            __vector_score: 0.1,
          },
        },
      ],
    });

    const results = await store.search([0.1, 0.2, 0.3, 0.4], 5);

    expect(results[0].payload.user_id).toBe("user-1");
    expect(results[0].payload.agent_id).toBe("agent-1");
    expect(results[0].payload.run_id).toBe("run-1");
    expect(results[0].payload).not.toHaveProperty("userId");
    expect(results[0].payload).not.toHaveProperty("agentId");
    expect(results[0].payload).not.toHaveProperty("runId");
  });

  test("get returns entity ids as snake_case", async () => {
    mockClient.exists.mockResolvedValue(1);
    mockClient.hGetAll.mockResolvedValue({
      memory_id: "mem-1",
      hash: "h1",
      memory: "likes coffee",
      created_at: "1700000000000",
      agent_id: "agent-1",
      run_id: "run-1",
      user_id: "user-1",
      metadata: "{}",
    });

    const result = await store.get("mem-1");

    expect(result?.payload.user_id).toBe("user-1");
    expect(result?.payload.agent_id).toBe("agent-1");
    expect(result?.payload.run_id).toBe("run-1");
    expect(result?.payload).not.toHaveProperty("userId");
    expect(result?.payload).not.toHaveProperty("agentId");
    expect(result?.payload).not.toHaveProperty("runId");
  });

  test("list returns entity ids as snake_case", async () => {
    mockClient.ft.search.mockResolvedValue({
      total: 1,
      documents: [
        {
          id: "mem0:test:mem-1",
          value: {
            memory_id: "mem-1",
            hash: "h1",
            memory: "likes coffee",
            created_at: "1700000000000",
            agent_id: "agent-1",
            run_id: "run-1",
            user_id: "user-1",
            metadata: "{}",
          },
        },
      ],
    });

    const [items] = await store.list();

    expect(items[0].payload.user_id).toBe("user-1");
    expect(items[0].payload.agent_id).toBe("agent-1");
    expect(items[0].payload.run_id).toBe("run-1");
    expect(items[0].payload).not.toHaveProperty("userId");
    expect(items[0].payload).not.toHaveProperty("agentId");
    expect(items[0].payload).not.toHaveProperty("runId");
  });
});
