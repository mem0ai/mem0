import { RedisDB } from "../src/vector_stores/redis";

jest.mock("redis", () => ({
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
    hGetAll: jest.fn(),
    del: jest.fn(),
    exists: jest.fn(),
    quit: jest.fn(),
  })),
}));

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

    expect(mockClient.hSet).toHaveBeenCalledTimes(1);
    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.memory_id).toBe("entity-1");
    expect(entry.memory).toBe("OpenAI");
    expect(entry.hash).toBe("");
    expect(entry.created_at).toBe(0);
    expect(entry.updated_at).toBe(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
    expect(Number.isNaN(entry.updated_at)).toBe(false);
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

    const call = mockClient.hSet.mock.calls[0];
    const entry = call[1];

    expect(entry.hash).toBe("abc123");
    expect(entry.memory).toBe("likes coffee");
    expect(entry.created_at).toBeGreaterThan(0);
    expect(entry.updated_at).toBeGreaterThan(0);
    expect(Number.isNaN(entry.created_at)).toBe(false);
    expect(Number.isNaN(entry.updated_at)).toBe(false);
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

  // Entity ids are part of the canonical payload contract in snake_case:
  // index.ts and the other stores read payload.user_id, not payload.userId.
  // Timestamps stay camelCase (createdAt). Before the fix, the whole payload
  // was run through toCamelCase, renaming user_id -> userId, which dropped the
  // ids from results and leaked them into metadata.
  const CREATED_AT_MS = 1719316800000;

  test("search returns entity ids in snake_case with camelCase timestamps", async () => {
    mockClient.ft.search.mockResolvedValueOnce({
      total: 1,
      documents: [
        {
          id: "mem0:test:mem-1",
          value: {
            memory_id: "mem-1",
            hash: "h1",
            memory: "likes coffee",
            created_at: String(CREATED_AT_MS),
            user_id: "test_user",
            agent_id: "agent_1",
            metadata: JSON.stringify({ source: "chat" }),
            __vector_score: "0.1",
          },
        },
      ],
    });

    const results = await store.search([0.1, 0.2, 0.3, 0.4], 5, {
      userId: "test_user",
    });

    expect(results).toHaveLength(1);
    const payload = results[0].payload;
    expect(payload.user_id).toBe("test_user");
    expect(payload.agent_id).toBe("agent_1");
    expect(payload.userId).toBeUndefined();
    expect(payload.agentId).toBeUndefined();
    expect(payload.createdAt).toBe(new Date(CREATED_AT_MS).toISOString());
    expect(payload.source).toBe("chat");
  });

  test("list returns entity ids in snake_case with camelCase timestamps", async () => {
    mockClient.ft.search.mockResolvedValueOnce({
      total: 1,
      documents: [
        {
          id: "mem0:test:mem-1",
          value: {
            memory_id: "mem-1",
            hash: "h1",
            memory: "likes coffee",
            created_at: String(CREATED_AT_MS),
            user_id: "test_user",
            run_id: "run_1",
            metadata: JSON.stringify({ source: "chat" }),
          },
        },
      ],
    });

    const [items, total] = await store.list({ userId: "test_user" }, 100);

    expect(total).toBe(1);
    const payload = items[0].payload;
    expect(payload.user_id).toBe("test_user");
    expect(payload.run_id).toBe("run_1");
    expect(payload.userId).toBeUndefined();
    expect(payload.runId).toBeUndefined();
    expect(payload.createdAt).toBe(new Date(CREATED_AT_MS).toISOString());
  });

  test("get returns entity ids in snake_case with camelCase timestamps", async () => {
    mockClient.exists.mockResolvedValueOnce(1);
    mockClient.hGetAll.mockResolvedValueOnce({
      memory_id: "mem-1",
      hash: "h1",
      memory: "likes coffee",
      created_at: String(CREATED_AT_MS),
      user_id: "test_user",
      agent_id: "agent_1",
      metadata: JSON.stringify({ source: "chat" }),
    });

    const result = await store.get("mem-1");

    expect(result).not.toBeNull();
    const payload = result!.payload;
    expect(payload.user_id).toBe("test_user");
    expect(payload.agent_id).toBe("agent_1");
    expect(payload.userId).toBeUndefined();
    expect(payload.agentId).toBeUndefined();
    expect(payload.createdAt).toBe(new Date(CREATED_AT_MS).toISOString());
    expect(payload.source).toBe("chat");
  });
});
