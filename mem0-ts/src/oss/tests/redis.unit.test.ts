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

describe("RedisDB – '*' wildcard filter means field-exists (mem0ai/mem0#6539)", () => {
  let store: RedisDB;
  let mockClient: any;

  beforeAll(async () => {
    store = createStore();
    await store.initialize();
    mockClient = (store as any).client;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockClient.ft.search.mockResolvedValue({ documents: [], total: 0 });
  });

  test("search translates '*' into a tag wildcard, not a literal tag", async () => {
    await store.search([0.1, 0.2, 0.3, 0.4], 5, { agentId: "*" });

    const [, queryString] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toContain("@agent_id:{w'*'}");
    expect(queryString).not.toContain("\\*");
  });

  test("search combines wildcard with tag equality", async () => {
    await store.search([0.1, 0.2, 0.3, 0.4], 5, {
      userId: "alice",
      agentId: "*",
    });

    const [, queryString] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toContain("@user_id:{alice}");
    expect(queryString).toContain("@agent_id:{w'*'}");
  });

  test("list translates '*' into a tag wildcard and sends DIALECT 2", async () => {
    await store.list({ agentId: "*" });

    const [, queryString, options] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toBe("@agent_id:{w'*'}");
    // The w'...' syntax requires DIALECT 2 and node-redis does not send
    // DIALECT unless asked.
    expect(options.DIALECT).toBe(2);
  });

  test("list without wildcard keeps its previous query shape", async () => {
    await store.list({ userId: "alice" });

    const [, queryString, options] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toBe("@user_id:{alice}");
    expect(options.DIALECT).toBeUndefined();
  });
});

describe("RedisDB – KNN prefilter parenthesization", () => {
  let store: RedisDB;
  let mockClient: any;

  beforeAll(async () => {
    store = createStore();
    await store.initialize();
    mockClient = (store as any).client;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockClient.ft.search.mockResolvedValue({ documents: [], total: 0 });
  });

  test("multi-filter search wraps the prefilter in parentheses", async () => {
    // RediSearch rejects a space-joined multi-condition prefilter placed
    // directly before =>[KNN ...] with a syntax error, so any search with
    // two or more filters failed outright.
    await store.search([0.1, 0.2, 0.3, 0.4], 5, {
      userId: "alice",
      agentId: "a1",
    });

    const [, queryString] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toMatch(/^\(.+\) =>\[KNN /);
  });

  test("unfiltered search keeps the match-all prefilter", async () => {
    await store.search([0.1, 0.2, 0.3, 0.4], 5);

    const [, queryString] = mockClient.ft.search.mock.calls[0];
    expect(queryString).toMatch(/^\* =>\[KNN /);
  });
});
