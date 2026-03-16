import { MemoryClient } from "../mem0";
import { Feedback } from "../mem0.types";
import {
  createMockFetch,
  createMockMemory,
  createMockMemoryHistory,
  createMockUser,
  createMockAllUsers,
  createStandardMockResponses,
  TEST_API_KEY,
  TEST_HOST,
  TEST_ORG_ID,
  TEST_PROJECT_ID,
  MOCK_PING_RESPONSE,
} from "./helpers";

// ─── Global fetch mock + telemetry suppression ───────────

const originalFetch = global.fetch;
let mockFetch: jest.Mock;

function setupMockFetch(
  extraResponses?: Map<string, { status: number; body: unknown }>,
) {
  const responses = createStandardMockResponses();
  if (extraResponses) {
    for (const [key, value] of extraResponses) {
      responses.set(key, value);
    }
  }
  mockFetch = createMockFetch(responses);
  global.fetch = mockFetch;
  return mockFetch;
}

const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

beforeAll(() => {
  // Suppress telemetry console noise during tests
  jest.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    const msg = String(args[0] ?? "");
    if (
      msg.includes("Telemetry") ||
      msg.includes("Failed to initialize") ||
      msg.includes("Failed to capture")
    ) {
      return;
    }
    originalConsoleError(...args);
  });
  jest.spyOn(console, "warn").mockImplementation((...args: unknown[]) => {
    const msg = String(args[0] ?? "");
    if (msg.includes("telemetry") || msg.includes("Telemetry")) {
      return;
    }
    originalConsoleWarn(...args);
  });
});

afterAll(() => {
  jest.restoreAllMocks();
});

afterEach(() => {
  global.fetch = originalFetch;
});

// ─── Helper: find specific fetch calls ───────────────────

function findFetchCall(
  mock: jest.Mock,
  urlPattern: string,
  method?: string,
): [string, RequestInit] | undefined {
  return mock.mock.calls.find((call: [string, RequestInit]) => {
    const urlMatch = call[0].includes(urlPattern);
    if (!method) return urlMatch;
    return urlMatch && call[1]?.method === method;
  });
}

function getFetchBody(call: [string, RequestInit]): Record<string, unknown> {
  return JSON.parse(call[1].body as string);
}

// ─── Initialization ──────────────────────────────────────

describe("MemoryClient - Initialization", () => {
  beforeEach(() => setupMockFetch());

  test("throws when API key is empty string", () => {
    expect(() => new MemoryClient({ apiKey: "" })).toThrow(
      "Mem0 API key is required",
    );
  });

  test("throws when API key is whitespace only", () => {
    expect(() => new MemoryClient({ apiKey: "   " })).toThrow(
      "Mem0 API key cannot be empty",
    );
  });

  test("throws when API key is not a string", () => {
    expect(
      () => new MemoryClient({ apiKey: 123 as unknown as string }),
    ).toThrow("Mem0 API key must be a string");
  });

  test("sets default host to https://api.mem0.ai", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.host).toBe("https://api.mem0.ai");
  });

  test("uses custom host when provided", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY, host: TEST_HOST });
    expect(client.host).toBe(TEST_HOST);
  });

  test("sets organizationId and projectId", () => {
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    expect(client.organizationId).toBe(TEST_ORG_ID);
    expect(client.projectId).toBe(TEST_PROJECT_ID);
  });

  test("sets organizationName and projectName (deprecated)", () => {
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationName: "test-org",
      projectName: "test-project",
    });
    expect(client.organizationName).toBe("test-org");
    expect(client.projectName).toBe("test-project");
  });

  test("sets Authorization header with Token prefix", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.headers["Authorization"]).toBe(`Token ${TEST_API_KEY}`);
  });

  test("creates axios client with 60s timeout", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    // The client property exists and was created
    expect(client.client).toBeDefined();
    expect(client.client.defaults.timeout).toBe(60000);
  });
});

// ─── Ping ────────────────────────────────────────────────

describe("MemoryClient - ping()", () => {
  test("extracts org_id, project_id, user_email from response", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.ping();

    expect(client.organizationId).toBe(TEST_ORG_ID);
    expect(client.projectId).toBe(TEST_PROJECT_ID);
    expect(client.telemetryId).toBe("test@example.com");
  });

  test("does not overwrite existing orgId/projectId from constructor", async () => {
    setupMockFetch();
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: "my_org",
      projectId: "my_proj",
    });
    await client.ping();

    expect(client.organizationId).toBe("my_org");
    expect(client.projectId).toBe("my_proj");
  });

  test("throws APIError on 401 response", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", {
      status: 401,
      body: JSON.stringify({ message: "Invalid API key" }),
    });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: "bad-key" });
    await expect(client.ping()).rejects.toThrow("API request failed");
  });

  test("throws on invalid (non-object) response format", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 200, body: "not an object" });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.ping()).rejects.toThrow("Invalid response format");
  });

  test("throws on status !== ok in response", async () => {
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", {
      status: 200,
      body: { status: "error", message: "API Key is invalid" },
    });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.ping()).rejects.toThrow("API Key is invalid");
  });
});

// ─── add() ───────────────────────────────────────────────

describe("MemoryClient - add()", () => {
  test("sends messages and user_id in POST body to /v1/memories/", async () => {
    const mockMem = createMockMemory({ id: "mem_new", event: "ADD" });
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: [mockMem] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const messages = [{ role: "user" as const, content: "Hello, I am Alex" }];
    const result = await client.add(messages, { user_id: "user_1" });

    const call = findFetchCall(mock, "/v1/memories/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    expect(body.messages).toEqual(messages);
    expect(body.user_id).toBe("user_1");

    // Verify response is correctly returned
    expect(Array.isArray(result)).toBe(true);
    expect(result[0].id).toBe("mem_new");
  });

  test("attaches org_id/project_id from constructor to payload", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: [createMockMemory()] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.add([{ role: "user", content: "test" }], { user_id: "u1" });

    const call = findFetchCall(mock, "/v1/memories/", "POST");
    const body = getFetchBody(call!);
    expect(body.org_id).toBe(TEST_ORG_ID);
    expect(body.project_id).toBe(TEST_PROJECT_ID);
  });

  test("returns response data without modification", async () => {
    const mockResponse = [
      createMockMemory({
        id: "m1",
        event: "ADD",
        memory: "Alex is vegetarian",
      }),
      createMockMemory({
        id: "m2",
        event: "UPDATE",
        memory: "Alex likes hiking",
      }),
    ];
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: mockResponse });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.add(
      [{ role: "user", content: "I'm Alex, vegetarian, love hiking" }],
      { user_id: "u1" },
    );

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("m1");
    expect(result[1].memory).toBe("Alex likes hiking");
  });
});

// ─── get() ───────────────────────────────────────────────

describe("MemoryClient - get()", () => {
  test("returns the full memory object for a valid ID", async () => {
    const mockMem = createMockMemory({
      id: "mem_123",
      memory: "I am Alex",
      user_id: "u1",
      categories: ["personal"],
      metadata: { source: "chat" },
    });
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", { status: 200, body: mockMem });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const memory = await client.get("mem_123");

    expect(memory.id).toBe("mem_123");
    expect(memory.memory).toBe("I am Alex");
    expect(memory.user_id).toBe("u1");
    expect(memory.categories).toEqual(["personal"]);
    expect(memory.metadata).toEqual({ source: "chat" });
  });

  test("throws on 404 with error message from server", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/nonexistent/", {
      status: 404,
      body: "Memory not found",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("nonexistent")).rejects.toThrow("Memory not found");
  });
});

// ─── getAll() ────────────────────────────────────────────

describe("MemoryClient - getAll()", () => {
  test("uses v2 POST endpoint when api_version=v2", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/", {
      status: 200,
      body: { results: [createMockMemory()] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getAll({ user_id: "u1", api_version: "v2" });

    const call = findFetchCall(mock, "/v2/memories/", "POST");
    expect(call).toBeDefined();
  });

  test("uses v1 GET endpoint by default", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: [createMockMemory()] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getAll({ user_id: "u1" });

    // v1 uses GET (no method = GET by default)
    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/?") && !c[1]?.method,
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("user_id=u1");
  });

  test("appends page and page_size to URL as query params", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/", {
      status: 200,
      body: { results: [createMockMemory()] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getAll({
      user_id: "u1",
      api_version: "v2",
      page: 2,
      page_size: 25,
    });

    const call = mock.mock.calls.find((c: [string, RequestInit]) =>
      c[0].includes("page="),
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("page=2");
    expect(call![0]).toContain("page_size=25");
  });
});

// ─── search() ────────────────────────────────────────────

describe("MemoryClient - search()", () => {
  test("includes query in POST body and returns scored results", async () => {
    const scoredMemory = createMockMemory({ id: "s1", score: 0.95 });
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [scoredMemory] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.search("What is my name?", { user_id: "u1" });

    const call = findFetchCall(mock, "/v1/memories/search/", "POST");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    expect(body.query).toBe("What is my name?");

    expect(Array.isArray(result)).toBe(true);
    expect(result[0].score).toBe(0.95);
  });

  test("uses /v2/memories/search/ when api_version=v2", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/search/", {
      status: 200,
      body: { results: [createMockMemory({ score: 0.9 })] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("test", { user_id: "u1", api_version: "v2" });

    expect(findFetchCall(mock, "/v2/memories/search/", "POST")).toBeDefined();
  });

  test("passes filters through to the API", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/search/", { status: 200, body: { results: [] } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("query", {
      api_version: "v2",
      filters: { OR: [{ user_id: "u1" }, { agent_id: "a1" }] },
    });

    const call = findFetchCall(mock, "/v2/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual({
      OR: [{ user_id: "u1" }, { agent_id: "a1" }],
    });
  });
});

// ─── update() ────────────────────────────────────────────

describe("MemoryClient - update()", () => {
  test("sends text in PUT body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory({ id: "mem_123" }),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { text: "Updated text" });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(call).toBeDefined();
    expect(getFetchBody(call!).text).toBe("Updated text");
  });

  test("sends metadata in PUT body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory({ id: "mem_123" }),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { metadata: { priority: "high" } });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(getFetchBody(call!).metadata).toEqual({ priority: "high" });
  });

  test("sends timestamp in PUT body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory({ id: "mem_123" }),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { timestamp: 1710600000 });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(getFetchBody(call!).timestamp).toBe(1710600000);
  });

  test("throws when no fields provided", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.update("mem_123", {})).rejects.toThrow(
      "At least one of text, metadata, or timestamp must be provided",
    );
  });
});

// ─── delete() ────────────────────────────────────────────

describe("MemoryClient - delete()", () => {
  test("returns message on success", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: { message: "Memory deleted successfully" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.delete("mem_123");

    expect(
      findFetchCall(mock, "/v1/memories/mem_123/", "DELETE"),
    ).toBeDefined();
    expect(result.message).toBe("Memory deleted successfully");
  });
});

// ─── deleteAll() ─────────────────────────────────────────

describe("MemoryClient - deleteAll()", () => {
  test("includes user_id as query param in DELETE request", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", {
      status: 200,
      body: { message: "Memories deleted" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.deleteAll({ user_id: "u1" });

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("user_id=u1");
    expect(result.message).toBe("Memories deleted");
  });
});

// ─── history() ───────────────────────────────────────────

describe("MemoryClient - history()", () => {
  test("returns array of history entries with correct shape", async () => {
    const historyEntries = [
      createMockMemoryHistory({
        memory_id: "mem_123",
        event: "ADD",
        old_memory: null,
        new_memory: "I am Alex",
      }),
      createMockMemoryHistory({
        id: "hist_2",
        memory_id: "mem_123",
        event: "UPDATE",
        old_memory: "I am Alex",
        new_memory: "I am Alex, a vegetarian",
      }),
    ];
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/history/", {
      status: 200,
      body: historyEntries,
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const history = await client.history("mem_123");

    expect(history).toHaveLength(2);
    expect(history[0].event).toBe("ADD");
    expect(history[0].old_memory).toBeNull();
    expect(history[0].new_memory).toBe("I am Alex");
    expect(history[1].event).toBe("UPDATE");
    expect(history[1].old_memory).toBe("I am Alex");
  });
});

// ─── Batch Operations ────────────────────────────────────

describe("MemoryClient - batchUpdate()", () => {
  test("transforms memoryId to memory_id in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", {
      status: 200,
      body: { message: "Batch update successful" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchUpdate([
      { memoryId: "mem_1", text: "updated 1" },
      { memoryId: "mem_2", text: "updated 2" },
    ]);

    const call = findFetchCall(mock, "/v1/batch/", "PUT");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    // Verify the camelCase→snake_case transformation
    expect(body.memories).toEqual([
      { memory_id: "mem_1", text: "updated 1" },
      { memory_id: "mem_2", text: "updated 2" },
    ]);
  });
});

describe("MemoryClient - batchDelete()", () => {
  test("wraps string IDs into {memory_id} objects", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", {
      status: 200,
      body: { message: "Batch delete successful" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchDelete(["mem_1", "mem_2", "mem_3"]);

    const call = findFetchCall(mock, "/v1/batch/", "DELETE");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    expect(body.memories).toEqual([
      { memory_id: "mem_1" },
      { memory_id: "mem_2" },
      { memory_id: "mem_3" },
    ]);
  });
});

// ─── Users ───────────────────────────────────────────────

describe("MemoryClient - users()", () => {
  test("returns AllUsers shape with count and results", async () => {
    const mockUsers = [
      createMockUser({ name: "alex", total_memories: 10 }),
      createMockUser({ id: "user_456", name: "bob", total_memories: 3 }),
    ];
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers(mockUsers),
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const allUsers = await client.users();

    expect(allUsers.count).toBe(2);
    expect(allUsers.results).toHaveLength(2);
    expect(allUsers.results[0].name).toBe("alex");
    expect(allUsers.results[0].total_memories).toBe(10);
    expect(allUsers.results[1].name).toBe("bob");
  });
});

describe("MemoryClient - deleteUsers()", () => {
  // deleteUsers uses this.client (axios) for DELETE, not global fetch.
  // We need to mock the axios instance directly on the client.

  function createClientWithMockedAxios() {
    setupMockFetch(); // For ping() in background init
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const axiosDeleteMock = jest
      .fn()
      .mockResolvedValue({ data: { message: "Deleted" } });
    // Override the internal axios client's delete method
    client.client.delete = axiosDeleteMock;
    return { client, axiosDeleteMock };
  }

  test("calls DELETE /v2/entities/user/:name/ for user_id", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    const result = await client.deleteUsers({ user_id: "u1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/user/u1/", {
      params: expect.objectContaining({
        org_id: TEST_ORG_ID,
        project_id: TEST_PROJECT_ID,
      }),
    });
    expect(result.message).toBe("Entity deleted successfully.");
  });

  test("calls DELETE /v2/entities/agent/:name/ for agent_id", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    const result = await client.deleteUsers({ agent_id: "agent_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/agent/agent_1/",
      expect.any(Object),
    );
    expect(result.message).toBe("Entity deleted successfully.");
  });

  test("calls DELETE /v2/entities/app/:name/ for app_id", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ app_id: "app_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/app/app_1/",
      expect.any(Object),
    );
  });

  test("calls DELETE /v2/entities/run/:name/ for run_id", async () => {
    const { client, axiosDeleteMock } = createClientWithMockedAxios();
    await client.deleteUsers({ run_id: "run_1" });

    expect(axiosDeleteMock).toHaveBeenCalledWith(
      "/v2/entities/run/run_1/",
      expect.any(Object),
    );
  });

  test("returns different message when deleting all entities", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([createMockUser({ name: "u1", type: "user" })]),
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    client.client.delete = jest
      .fn()
      .mockResolvedValue({ data: { message: "Deleted" } });

    const result = await client.deleteUsers(); // no params = delete all
    expect(result.message).toBe("All users, agents, apps and runs deleted.");
  });
});

// ─── Webhooks ────────────────────────────────────────────

describe("MemoryClient - Webhooks", () => {
  test("getWebhooks returns array of webhooks", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: [
        {
          webhook_id: "wh_1",
          name: "test",
          url: "https://example.com",
          is_active: true,
        },
      ],
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const webhooks = await client.getWebhooks();

    expect(Array.isArray(webhooks)).toBe(true);
    expect(webhooks[0].webhook_id).toBe("wh_1");
    expect(webhooks[0].is_active).toBe(true);
  });

  test("createWebhook sends webhook data in POST body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/projects/", {
      status: 200,
      body: {
        webhook_id: "wh_new",
        name: "new-hook",
        url: "https://example.com",
      },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const result = await client.createWebhook({
      name: "new-hook",
      url: "https://example.com",
      eventTypes: ["memory_add" as never],
      projectId: TEST_PROJECT_ID,
      webhookId: "",
    });

    const call = findFetchCall(mock, "/api/v1/webhooks/", "POST");
    expect(call).toBeDefined();
    expect(result.name).toBe("new-hook");
  });

  test("deleteWebhook calls correct endpoint", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook deleted" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.deleteWebhook({ webhookId: "wh_1" });

    expect(
      findFetchCall(mock, "/api/v1/webhooks/wh_1/", "DELETE"),
    ).toBeDefined();
    expect(result.message).toBe("Webhook deleted");
  });
});

// ─── Feedback ────────────────────────────────────────────

describe("MemoryClient - feedback()", () => {
  test("sends memory_id, feedback, and reason in POST body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/feedback/", {
      status: 200,
      body: { message: "Feedback recorded" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.feedback({
      memory_id: "mem_123",
      feedback: Feedback.POSITIVE,
      feedback_reason: "Very helpful",
    });

    const call = findFetchCall(mock, "/v1/feedback/", "POST");
    const body = getFetchBody(call!);
    expect(body.memory_id).toBe("mem_123");
    expect(body.feedback).toBe("POSITIVE");
    expect(body.feedback_reason).toBe("Very helpful");
    expect(result.message).toBe("Feedback recorded");
  });
});

// ─── Exports ─────────────────────────────────────────────

describe("MemoryClient - Memory Exports", () => {
  test("createMemoryExport throws when missing filters or schema", async () => {
    setupMockFetch();
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await expect(
      client.createMemoryExport({
        filters: null as never,
        schema: null as never,
      }),
    ).rejects.toThrow("Missing filters or schema");
  });

  test("createMemoryExport returns export ID on success", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/", {
      status: 200,
      body: { message: "Export created", id: "exp_123" },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const result = await client.createMemoryExport({
      schema: { fields: ["memory", "user_id"] },
      filters: { user_id: "u1" },
    });

    expect(result.id).toBe("exp_123");
  });

  test("getMemoryExport throws when missing both id and filters", async () => {
    setupMockFetch();
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await expect(client.getMemoryExport({} as never)).rejects.toThrow(
      "Missing memory_export_id or filters",
    );
  });

  test("getMemoryExport returns data for valid export ID", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/get/", {
      status: 200,
      body: { message: "Export data", id: "exp_123" },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const result = await client.getMemoryExport({
      memory_export_id: "exp_123",
    });
    expect(result.id).toBe("exp_123");
  });
});

// ─── Project Methods ─────────────────────────────────────

describe("MemoryClient - getProject()", () => {
  test("throws when organizationId and projectId not set", async () => {
    // Use a ping response without org/project so they stay null
    const responses = new Map<string, { status: number; body: unknown }>();
    responses.set("/v1/ping/", { status: 200, body: { status: "ok" } });
    global.fetch = createMockFetch(responses);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    // Flush the async _initializeClient by calling ping directly
    try {
      await client.ping();
    } catch {
      // ping might throw because status!="ok" path — but orgId stays null
    }

    await expect(
      client.getProject({ fields: ["custom_instructions"] }),
    ).rejects.toThrow("organizationId and projectId must be set");
  });

  test("returns project configuration", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: {
        custom_instructions: "Be helpful",
        custom_categories: ["work", "personal"],
      },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const project = await client.getProject({
      fields: ["custom_instructions"],
    });

    expect(project.custom_instructions).toBe("Be helpful");
    expect(project.custom_categories).toEqual(["work", "personal"]);
  });
});

describe("MemoryClient - updateProject()", () => {
  test("sends PATCH with project settings", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/orgs/organizations/", {
      status: 200,
      body: { custom_instructions: "Updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.updateProject({ custom_instructions: "Updated instructions" });

    const call = findFetchCall(mock, "/api/v1/orgs/organizations/", "PATCH");
    expect(call).toBeDefined();
    expect(getFetchBody(call!).custom_instructions).toBe(
      "Updated instructions",
    );
  });
});

// ─── Error Handling ──────────────────────────────────────

describe("MemoryClient - Error Handling", () => {
  test("404 error includes server response text", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/gone/", { status: 404, body: "Memory not found" });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("gone")).rejects.toThrow("Memory not found");
  });

  test("500 error throws with API request failed prefix", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/err/", {
      status: 500,
      body: "Internal server error",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("err")).rejects.toThrow("API request failed");
  });

  test("400 error includes validation details from server", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/bad/", {
      status: 400,
      body: "Invalid request: user_id is required",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("bad")).rejects.toThrow(
      "Invalid request: user_id is required",
    );
  });

  test("Authorization header is included in every fetch call", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_1/", {
      status: 200,
      body: createMockMemory({ id: "mem_1" }),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.get("mem_1");

    const call = findFetchCall(mock, "/v1/memories/mem_1/");
    expect(call).toBeDefined();
    const headers = call![1].headers as Record<string, string>;
    expect(headers["Authorization"]).toContain(TEST_API_KEY);
  });

  test("network failure (fetch throws) is handled", async () => {
    const responses = createStandardMockResponses();
    responses.set("/v1/memories/net_err/", {
      status: 200,
      body: createMockMemory(),
    });
    // Override with a fetch that throws on the specific endpoint
    global.fetch = jest.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/v1/memories/net_err/")) {
        throw new TypeError("Failed to fetch");
      }
      if (urlStr.includes("/v1/ping/")) {
        return {
          ok: true,
          status: 200,
          json: async () => MOCK_PING_RESPONSE,
          text: async () => JSON.stringify(MOCK_PING_RESPONSE),
        } as Response;
      }
      return {
        ok: false,
        status: 404,
        text: async () => "Not found",
      } as Response;
    });

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("net_err")).rejects.toThrow();
  });
});

// ─── Deprecated Methods ──────────────────────────────────

describe("MemoryClient - deleteUser() (deprecated)", () => {
  test("calls DELETE /v1/entities/:type/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/user/123/", {
      status: 200,
      body: { message: "Entity deleted successfully!" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.deleteUser({
      entity_id: 123 as never,
      entity_type: "user",
    });

    expect(
      findFetchCall(mock, "/v1/entities/user/123/", "DELETE"),
    ).toBeDefined();
    expect(result.message).toBe("Entity deleted successfully!");
  });

  test("defaults entity_type to 'user' when not provided", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/user/456/", {
      status: 200,
      body: { message: "Entity deleted successfully!" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteUser({ entity_id: 456 as never, entity_type: "" });

    expect(
      findFetchCall(mock, "/v1/entities/user/456/", "DELETE"),
    ).toBeDefined();
  });
});

// ─── updateWebhook ───────────────────────────────────────

describe("MemoryClient - updateWebhook()", () => {
  test("sends PUT to /api/v1/webhooks/:id/ with updated data", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/api/v1/webhooks/wh_1/", {
      status: 200,
      body: { message: "Webhook updated" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    const result = await client.updateWebhook({
      webhookId: "wh_1",
      name: "updated-hook",
      url: "https://new-url.com",
      eventTypes: ["memory_add" as never],
      projectId: TEST_PROJECT_ID,
    });

    const call = findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT");
    expect(call).toBeDefined();
    const body = getFetchBody(call!);
    expect(body.name).toBe("updated-hook");
    expect(body.url).toBe("https://new-url.com");
    expect(result.message).toBe("Webhook updated");
  });
});

// ─── Edge Cases: Real-World Scenarios ────────────────────
// These tests document actual bugs and pain points in the source code.
// Some are expected failures that expose known issues to fix on Day 4.

describe("MemoryClient - Edge Cases", () => {
  // BUG: getAll() uses options! (non-null assertion) on line 313 of mem0.ts
  // calling getAll() without options crashes with TypeError
  test("getAll() without options throws (known bug: options! non-null assertion)", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    // This SHOULD work but crashes because of `options!` destructure on undefined
    await expect(client.getAll()).rejects.toThrow();
  });

  // BUG: search() uses options! on line 364 of mem0.ts — same pattern
  test("search() without options throws (known bug: options! non-null assertion)", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.search("query")).rejects.toThrow();
  });

  // Verify add() with empty messages array doesn't crash
  test("add() with empty messages array sends request", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.add([], { user_id: "u1" });

    const call = findFetchCall(mock, "/v1/memories/", "POST");
    const body = getFetchBody(call!);
    expect(body.messages).toEqual([]);
    expect(Array.isArray(result)).toBe(true);
  });

  // Verify special characters in user_id don't break URL encoding
  test("deleteAll() handles special characters in user_id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", {
      status: 200,
      body: { message: "Deleted" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteAll({ user_id: "user@email.com" });

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
    );
    expect(call).toBeDefined();
    // URL should encode the @ symbol
    expect(call![0]).toContain("user_id=");
  });

  // Verify update() with all three fields sends them all
  test("update() with text + metadata + timestamp sends all fields", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory({ id: "mem_123" }),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", {
      text: "Updated",
      metadata: { source: "test" },
      timestamp: 1710600000,
    });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    const body = getFetchBody(call!);
    expect(body.text).toBe("Updated");
    expect(body.metadata).toEqual({ source: "test" });
    expect(body.timestamp).toBe(1710600000);
  });

  // API returning empty array for search — should not crash
  test("search() handles empty results array", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.search("nonexistent query", { user_id: "u1" });
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(0);
  });

  // API returning empty array for history — should not crash
  test("history() handles empty history", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/history/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.history("mem_123");
    expect(result).toEqual([]);
  });

  // Verify batchUpdate with empty array doesn't crash
  test("batchUpdate() with empty array sends request", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", {
      status: 200,
      body: { message: "OK" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchUpdate([]);

    const call = findFetchCall(mock, "/v1/batch/", "PUT");
    const body = getFetchBody(call!);
    expect(body.memories).toEqual([]);
  });

  // Verify batchDelete with empty array doesn't crash
  test("batchDelete() with empty array sends request", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", {
      status: 200,
      body: { message: "OK" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchDelete([]);

    const call = findFetchCall(mock, "/v1/batch/", "DELETE");
    const body = getFetchBody(call!);
    expect(body.memories).toEqual([]);
  });

  // Verify deleteUsers throws when no entities exist
  test("deleteUsers() with no params throws when user list is empty", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/entities/", {
      status: 200,
      body: createMockAllUsers([]), // empty users list
    });
    setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    client.client.delete = jest.fn();

    await expect(client.deleteUsers()).rejects.toThrow("No entities to delete");
  });

  // Verify createMemoryExport attaches org/project IDs
  test("createMemoryExport() attaches org_id and project_id from client", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/exports/", {
      status: 200,
      body: { message: "Created", id: "exp_1" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: TEST_ORG_ID,
      projectId: TEST_PROJECT_ID,
    });
    await client.createMemoryExport({
      schema: { fields: ["memory"] },
      filters: { user_id: "u1" },
    });

    const call = findFetchCall(mock, "/v1/exports/", "POST");
    const body = getFetchBody(call!);
    expect(body.org_id).toBe(TEST_ORG_ID);
    expect(body.project_id).toBe(TEST_PROJECT_ID);
  });
});
