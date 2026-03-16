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

  describe("sets organizationId and projectId", () => {
    let client: MemoryClient;

    beforeEach(() => {
      client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationId: TEST_ORG_ID,
        projectId: TEST_PROJECT_ID,
      });
    });

    test("sets organizationId from constructor", () => {
      expect(client.organizationId).toBe(TEST_ORG_ID);
    });

    test("sets projectId from constructor", () => {
      expect(client.projectId).toBe(TEST_PROJECT_ID);
    });
  });

  describe("sets organizationName and projectName (deprecated)", () => {
    let client: MemoryClient;

    beforeEach(() => {
      client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationName: "test-org",
        projectName: "test-project",
      });
    });

    test("sets organizationName from constructor", () => {
      expect(client.organizationName).toBe("test-org");
    });

    test("sets projectName from constructor", () => {
      expect(client.projectName).toBe("test-project");
    });
  });

  test("sets Authorization header with Token prefix", () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    expect(client.headers["Authorization"]).toBe(`Token ${TEST_API_KEY}`);
  });

  describe("creates axios client", () => {
    let client: MemoryClient;

    beforeEach(() => {
      client = new MemoryClient({ apiKey: TEST_API_KEY });
    });

    test("client property is defined", () => {
      expect(client.client).toBeDefined();
    });

    test("timeout is set to 60s", () => {
      expect(client.client.defaults.timeout).toBe(60000);
    });
  });
});

// ─── Ping ────────────────────────────────────────────────

describe("MemoryClient - ping()", () => {
  describe("extracts fields from response", () => {
    let client: MemoryClient;

    beforeEach(async () => {
      setupMockFetch();
      client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.ping();
    });

    test("sets organizationId from response", () => {
      expect(client.organizationId).toBe(TEST_ORG_ID);
    });

    test("sets projectId from response", () => {
      expect(client.projectId).toBe(TEST_PROJECT_ID);
    });

    test("sets telemetryId from user_email in response", () => {
      expect(client.telemetryId).toBe("test@example.com");
    });
  });

  describe("does not overwrite existing orgId/projectId from constructor", () => {
    let client: MemoryClient;

    beforeEach(async () => {
      setupMockFetch();
      client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationId: "my_org",
        projectId: "my_proj",
      });
      await client.ping();
    });

    test("preserves organizationId from constructor", () => {
      expect(client.organizationId).toBe("my_org");
    });

    test("preserves projectId from constructor", () => {
      expect(client.projectId).toBe("my_proj");
    });
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
  describe("sends messages and user_id in POST body to /v1/memories/", () => {
    let mock: jest.Mock;
    let result: any;
    const messages = [{ role: "user" as const, content: "Hello, I am Alex" }];

    beforeEach(async () => {
      const mockMem = createMockMemory({ id: "mem_new", event: "ADD" });
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/", { status: 200, body: [mockMem] });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.add(messages, { user_id: "user_1" });
    });

    test("sends POST to /v1/memories/", () => {
      expect(findFetchCall(mock, "/v1/memories/", "POST")).toBeDefined();
    });

    test("includes messages in request body", () => {
      const call = findFetchCall(mock, "/v1/memories/", "POST");
      expect(getFetchBody(call!).messages).toEqual(messages);
    });

    test("includes user_id in request body", () => {
      const call = findFetchCall(mock, "/v1/memories/", "POST");
      expect(getFetchBody(call!).user_id).toBe("user_1");
    });

    test("returns an array", () => {
      expect(Array.isArray(result)).toBe(true);
    });

    test("returns memory with correct id", () => {
      expect(result[0].id).toBe("mem_new");
    });
  });

  describe("attaches org_id/project_id from constructor to payload", () => {
    let body: Record<string, unknown>;

    beforeEach(async () => {
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
      body = getFetchBody(call!);
    });

    test("includes org_id in request body", () => {
      expect(body.org_id).toBe(TEST_ORG_ID);
    });

    test("includes project_id in request body", () => {
      expect(body.project_id).toBe(TEST_PROJECT_ID);
    });
  });

  describe("returns response data without modification", () => {
    let result: any;

    beforeEach(async () => {
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
      result = await client.add(
        [{ role: "user", content: "I'm Alex, vegetarian, love hiking" }],
        { user_id: "u1" },
      );
    });

    test("returns two items", () => {
      expect(result).toHaveLength(2);
    });

    test("first item has correct id", () => {
      expect(result[0].id).toBe("m1");
    });

    test("second item has correct memory text", () => {
      expect(result[1].memory).toBe("Alex likes hiking");
    });
  });
});

// ─── get() ───────────────────────────────────────────────

describe("MemoryClient - get()", () => {
  describe("returns the full memory object for a valid ID", () => {
    let memory: any;

    beforeEach(async () => {
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
      memory = await client.get("mem_123");
    });

    test("returns correct id", () => {
      expect(memory.id).toBe("mem_123");
    });

    test("returns correct memory text", () => {
      expect(memory.memory).toBe("I am Alex");
    });

    test("returns correct user_id", () => {
      expect(memory.user_id).toBe("u1");
    });

    test("returns correct categories", () => {
      expect(memory.categories).toEqual(["personal"]);
    });

    test("returns correct metadata", () => {
      expect(memory.metadata).toEqual({ source: "chat" });
    });
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

  describe("uses v1 GET endpoint by default", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/", { status: 200, body: [createMockMemory()] });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.getAll({ user_id: "u1" });

      // v1 uses GET (no method = GET by default)
      call = mock.mock.calls.find(
        (c: [string, RequestInit]) =>
          c[0].includes("/v1/memories/?") && !c[1]?.method,
      );
    });

    test("sends GET request to /v1/memories/", () => {
      expect(call).toBeDefined();
    });

    test("includes user_id as query param", () => {
      expect(call![0]).toContain("user_id=u1");
    });
  });

  describe("appends page and page_size to URL as query params", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
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

      call = mock.mock.calls.find((c: [string, RequestInit]) =>
        c[0].includes("page="),
      );
    });

    test("fetch call with page param exists", () => {
      expect(call).toBeDefined();
    });

    test("includes page=2 in URL", () => {
      expect(call![0]).toContain("page=2");
    });

    test("includes page_size=25 in URL", () => {
      expect(call![0]).toContain("page_size=25");
    });
  });
});

// ─── search() ────────────────────────────────────────────

describe("MemoryClient - search()", () => {
  describe("includes query in POST body and returns scored results", () => {
    let mock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const scoredMemory = createMockMemory({ id: "s1", score: 0.95 });
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/search/", { status: 200, body: [scoredMemory] });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.search("What is my name?", { user_id: "u1" });
    });

    test("sends POST to /v1/memories/search/", () => {
      expect(findFetchCall(mock, "/v1/memories/search/", "POST")).toBeDefined();
    });

    test("includes query in request body", () => {
      const call = findFetchCall(mock, "/v1/memories/search/", "POST");
      expect(getFetchBody(call!).query).toBe("What is my name?");
    });

    test("returns an array", () => {
      expect(Array.isArray(result)).toBe(true);
    });

    test("first result has correct score", () => {
      expect(result[0].score).toBe(0.95);
    });
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
  describe("sends text in PUT body", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/mem_123/", {
        status: 200,
        body: createMockMemory({ id: "mem_123" }),
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.update("mem_123", { text: "Updated text" });

      call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    });

    test("sends PUT request to /v1/memories/mem_123/", () => {
      expect(call).toBeDefined();
    });

    test("includes text in request body", () => {
      expect(getFetchBody(call!).text).toBe("Updated text");
    });
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
  describe("returns message on success", () => {
    let mock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/mem_123/", {
        status: 200,
        body: { message: "Memory deleted successfully" },
      });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.delete("mem_123");
    });

    test("sends DELETE to /v1/memories/mem_123/", () => {
      expect(
        findFetchCall(mock, "/v1/memories/mem_123/", "DELETE"),
      ).toBeDefined();
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Memory deleted successfully");
    });
  });
});

// ─── deleteAll() ─────────────────────────────────────────

describe("MemoryClient - deleteAll()", () => {
  describe("includes user_id as query param in DELETE request", () => {
    let call: [string, RequestInit] | undefined;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/", {
        status: 200,
        body: { message: "Memories deleted" },
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.deleteAll({ user_id: "u1" });

      call = mock.mock.calls.find(
        (c: [string, RequestInit]) =>
          c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
      );
    });

    test("sends DELETE request", () => {
      expect(call).toBeDefined();
    });

    test("includes user_id=u1 in URL", () => {
      expect(call![0]).toContain("user_id=u1");
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Memories deleted");
    });
  });
});

// ─── history() ───────────────────────────────────────────

describe("MemoryClient - history()", () => {
  describe("returns array of history entries with correct shape", () => {
    let history: any;

    beforeEach(async () => {
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
      history = await client.history("mem_123");
    });

    test("returns two entries", () => {
      expect(history).toHaveLength(2);
    });

    test("first entry has event ADD", () => {
      expect(history[0].event).toBe("ADD");
    });

    test("first entry has null old_memory", () => {
      expect(history[0].old_memory).toBeNull();
    });

    test("first entry has correct new_memory", () => {
      expect(history[0].new_memory).toBe("I am Alex");
    });

    test("second entry has event UPDATE", () => {
      expect(history[1].event).toBe("UPDATE");
    });

    test("second entry has correct old_memory", () => {
      expect(history[1].old_memory).toBe("I am Alex");
    });
  });
});

// ─── Batch Operations ────────────────────────────────────

describe("MemoryClient - batchUpdate()", () => {
  describe("transforms memoryId to memory_id in request body", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
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

      call = findFetchCall(mock, "/v1/batch/", "PUT");
    });

    test("sends PUT to /v1/batch/", () => {
      expect(call).toBeDefined();
    });

    test("transforms memoryId to memory_id in memories array", () => {
      const body = getFetchBody(call!);
      expect(body.memories).toEqual([
        { memory_id: "mem_1", text: "updated 1" },
        { memory_id: "mem_2", text: "updated 2" },
      ]);
    });
  });
});

describe("MemoryClient - batchDelete()", () => {
  describe("wraps string IDs into {memory_id} objects", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/batch/", {
        status: 200,
        body: { message: "Batch delete successful" },
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.batchDelete(["mem_1", "mem_2", "mem_3"]);

      call = findFetchCall(mock, "/v1/batch/", "DELETE");
    });

    test("sends DELETE to /v1/batch/", () => {
      expect(call).toBeDefined();
    });

    test("wraps IDs into memory_id objects in memories array", () => {
      const body = getFetchBody(call!);
      expect(body.memories).toEqual([
        { memory_id: "mem_1" },
        { memory_id: "mem_2" },
        { memory_id: "mem_3" },
      ]);
    });
  });
});

// ─── Users ───────────────────────────────────────────────

describe("MemoryClient - users()", () => {
  describe("returns AllUsers shape with count and results", () => {
    let allUsers: any;

    beforeEach(async () => {
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
      allUsers = await client.users();
    });

    test("returns count of 2", () => {
      expect(allUsers.count).toBe(2);
    });

    test("returns two results", () => {
      expect(allUsers.results).toHaveLength(2);
    });

    test("first user has name alex", () => {
      expect(allUsers.results[0].name).toBe("alex");
    });

    test("first user has 10 total_memories", () => {
      expect(allUsers.results[0].total_memories).toBe(10);
    });

    test("second user has name bob", () => {
      expect(allUsers.results[1].name).toBe("bob");
    });
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

  describe("calls DELETE for user_id", () => {
    let axiosDeleteMock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      ({ axiosDeleteMock } = createClientWithMockedAxios());
      const { client } = createClientWithMockedAxios();
      // Need fresh client reference
      axiosDeleteMock = jest
        .fn()
        .mockResolvedValue({ data: { message: "Deleted" } });
      client.client.delete = axiosDeleteMock;
      result = await client.deleteUsers({ user_id: "u1" });
    });

    test("calls DELETE /v2/entities/user/u1/ with correct params", () => {
      expect(axiosDeleteMock).toHaveBeenCalledWith("/v2/entities/user/u1/", {
        params: expect.objectContaining({
          org_id: TEST_ORG_ID,
          project_id: TEST_PROJECT_ID,
        }),
      });
    });

    test("returns correct success message", () => {
      expect(result.message).toBe("Entity deleted successfully.");
    });
  });

  describe("calls DELETE for agent_id", () => {
    let axiosDeleteMock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const { client } = createClientWithMockedAxios();
      axiosDeleteMock = jest
        .fn()
        .mockResolvedValue({ data: { message: "Deleted" } });
      client.client.delete = axiosDeleteMock;
      result = await client.deleteUsers({ agent_id: "agent_1" });
    });

    test("calls DELETE /v2/entities/agent/agent_1/", () => {
      expect(axiosDeleteMock).toHaveBeenCalledWith(
        "/v2/entities/agent/agent_1/",
        expect.any(Object),
      );
    });

    test("returns correct success message", () => {
      expect(result.message).toBe("Entity deleted successfully.");
    });
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
  describe("getWebhooks returns array of webhooks", () => {
    let webhooks: any;

    beforeEach(async () => {
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
      webhooks = await client.getWebhooks();
    });

    test("returns an array", () => {
      expect(Array.isArray(webhooks)).toBe(true);
    });

    test("first webhook has correct webhook_id", () => {
      expect(webhooks[0].webhook_id).toBe("wh_1");
    });

    test("first webhook is active", () => {
      expect(webhooks[0].is_active).toBe(true);
    });
  });

  describe("createWebhook sends webhook data in POST body", () => {
    let mock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/api/v1/webhooks/projects/", {
        status: 200,
        body: {
          webhook_id: "wh_new",
          name: "new-hook",
          url: "https://example.com",
        },
      });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationId: TEST_ORG_ID,
        projectId: TEST_PROJECT_ID,
      });
      result = await client.createWebhook({
        name: "new-hook",
        url: "https://example.com",
        eventTypes: ["memory_add" as never],
        projectId: TEST_PROJECT_ID,
        webhookId: "",
      });
    });

    test("sends POST to /api/v1/webhooks/", () => {
      expect(findFetchCall(mock, "/api/v1/webhooks/", "POST")).toBeDefined();
    });

    test("returns webhook with correct name", () => {
      expect(result.name).toBe("new-hook");
    });
  });

  describe("deleteWebhook calls correct endpoint", () => {
    let mock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/api/v1/webhooks/wh_1/", {
        status: 200,
        body: { message: "Webhook deleted" },
      });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.deleteWebhook({ webhookId: "wh_1" });
    });

    test("sends DELETE to /api/v1/webhooks/wh_1/", () => {
      expect(
        findFetchCall(mock, "/api/v1/webhooks/wh_1/", "DELETE"),
      ).toBeDefined();
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Webhook deleted");
    });
  });
});

// ─── Feedback ────────────────────────────────────────────

describe("MemoryClient - feedback()", () => {
  describe("sends memory_id, feedback, and reason in POST body", () => {
    let body: Record<string, unknown>;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/feedback/", {
        status: 200,
        body: { message: "Feedback recorded" },
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.feedback({
        memory_id: "mem_123",
        feedback: Feedback.POSITIVE,
        feedback_reason: "Very helpful",
      });

      const call = findFetchCall(mock, "/v1/feedback/", "POST");
      body = getFetchBody(call!);
    });

    test("includes memory_id in request body", () => {
      expect(body.memory_id).toBe("mem_123");
    });

    test("includes feedback in request body", () => {
      expect(body.feedback).toBe("POSITIVE");
    });

    test("includes feedback_reason in request body", () => {
      expect(body.feedback_reason).toBe("Very helpful");
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Feedback recorded");
    });
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

  describe("returns project configuration", () => {
    let project: any;

    beforeEach(async () => {
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
      project = await client.getProject({
        fields: ["custom_instructions"],
      });
    });

    test("returns correct custom_instructions", () => {
      expect(project.custom_instructions).toBe("Be helpful");
    });

    test("returns correct custom_categories", () => {
      expect(project.custom_categories).toEqual(["work", "personal"]);
    });
  });
});

describe("MemoryClient - updateProject()", () => {
  describe("sends PATCH with project settings", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
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
      await client.updateProject({
        custom_instructions: "Updated instructions",
      });

      call = findFetchCall(mock, "/api/v1/orgs/organizations/", "PATCH");
    });

    test("sends PATCH to /api/v1/orgs/organizations/", () => {
      expect(call).toBeDefined();
    });

    test("includes custom_instructions in request body", () => {
      expect(getFetchBody(call!).custom_instructions).toBe(
        "Updated instructions",
      );
    });
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

  describe("Authorization header is included in every fetch call", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/mem_1/", {
        status: 200,
        body: createMockMemory({ id: "mem_1" }),
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.get("mem_1");

      call = findFetchCall(mock, "/v1/memories/mem_1/");
    });

    test("fetch call to /v1/memories/mem_1/ exists", () => {
      expect(call).toBeDefined();
    });

    test("Authorization header contains API key", () => {
      const headers = call![1].headers as Record<string, string>;
      expect(headers["Authorization"]).toContain(TEST_API_KEY);
    });
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
  describe("calls DELETE /v1/entities/:type/:id/", () => {
    let mock: jest.Mock;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/entities/user/123/", {
        status: 200,
        body: { message: "Entity deleted successfully!" },
      });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.deleteUser({
        entity_id: 123 as never,
        entity_type: "user",
      });
    });

    test("sends DELETE to /v1/entities/user/123/", () => {
      expect(
        findFetchCall(mock, "/v1/entities/user/123/", "DELETE"),
      ).toBeDefined();
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Entity deleted successfully!");
    });
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
  describe("sends PUT to /api/v1/webhooks/:id/ with updated data", () => {
    let mock: jest.Mock;
    let result: any;
    let body: Record<string, unknown>;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/api/v1/webhooks/wh_1/", {
        status: 200,
        body: { message: "Webhook updated" },
      });
      mock = setupMockFetch(extra);

      const client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationId: TEST_ORG_ID,
        projectId: TEST_PROJECT_ID,
      });
      result = await client.updateWebhook({
        webhookId: "wh_1",
        name: "updated-hook",
        url: "https://new-url.com",
        eventTypes: ["memory_add" as never],
        projectId: TEST_PROJECT_ID,
      });

      const call = findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT");
      body = getFetchBody(call!);
    });

    test("sends PUT to /api/v1/webhooks/wh_1/", () => {
      expect(
        findFetchCall(mock, "/api/v1/webhooks/wh_1/", "PUT"),
      ).toBeDefined();
    });

    test("includes name in request body", () => {
      expect(body.name).toBe("updated-hook");
    });

    test("includes url in request body", () => {
      expect(body.url).toBe("https://new-url.com");
    });

    test("returns correct message", () => {
      expect(result.message).toBe("Webhook updated");
    });
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

  describe("add() with empty messages array sends request", () => {
    let body: Record<string, unknown>;
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/", { status: 200, body: [] });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.add([], { user_id: "u1" });

      const call = findFetchCall(mock, "/v1/memories/", "POST");
      body = getFetchBody(call!);
    });

    test("sends empty messages array in body", () => {
      expect(body.messages).toEqual([]);
    });

    test("returns an array", () => {
      expect(Array.isArray(result)).toBe(true);
    });
  });

  describe("deleteAll() handles special characters in user_id", () => {
    let call: [string, RequestInit] | undefined;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/", {
        status: 200,
        body: { message: "Deleted" },
      });
      const mock = setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      await client.deleteAll({ user_id: "user@email.com" });

      call = mock.mock.calls.find(
        (c: [string, RequestInit]) =>
          c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
      );
    });

    test("sends DELETE request", () => {
      expect(call).toBeDefined();
    });

    test("URL contains user_id param", () => {
      expect(call![0]).toContain("user_id=");
    });
  });

  describe("update() with text + metadata + timestamp sends all fields", () => {
    let body: Record<string, unknown>;

    beforeEach(async () => {
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
      body = getFetchBody(call!);
    });

    test("includes text in body", () => {
      expect(body.text).toBe("Updated");
    });

    test("includes metadata in body", () => {
      expect(body.metadata).toEqual({ source: "test" });
    });

    test("includes timestamp in body", () => {
      expect(body.timestamp).toBe(1710600000);
    });
  });

  describe("search() handles empty results array", () => {
    let result: any;

    beforeEach(async () => {
      const extra = new Map<string, { status: number; body: unknown }>();
      extra.set("/v1/memories/search/", { status: 200, body: [] });
      setupMockFetch(extra);

      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      result = await client.search("nonexistent query", { user_id: "u1" });
    });

    test("returns an array", () => {
      expect(Array.isArray(result)).toBe(true);
    });

    test("returns empty array", () => {
      expect(result).toHaveLength(0);
    });
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
  test("batchUpdate() with empty array sends empty memories", async () => {
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
  test("batchDelete() with empty array sends empty memories", async () => {
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

  describe("createMemoryExport() attaches org_id and project_id from client", () => {
    let body: Record<string, unknown>;

    beforeEach(async () => {
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
      body = getFetchBody(call!);
    });

    test("includes org_id in request body", () => {
      expect(body.org_id).toBe(TEST_ORG_ID);
    });

    test("includes project_id in request body", () => {
      expect(body.project_id).toBe(TEST_PROJECT_ID);
    });
  });
});
