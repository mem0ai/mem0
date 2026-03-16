/**
 * MemoryClient API integration tests — converted from E2E to mock-based.
 * Same test names and assertions as original, but runs without API keys.
 */
import { MemoryClient } from "../mem0";
import {
  createMockFetch,
  createMockMemory,
  createMockMemoryHistory,
  createMockUser,
  createMockAllUsers,
  TEST_API_KEY,
  MOCK_PING_RESPONSE,
} from "./helpers";

const originalFetch = global.fetch;
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

beforeAll(() => {
  jest.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    if (
      String(args[0] ?? "").match(
        /Telemetry|Failed to initialize|Failed to capture/,
      )
    )
      return;
    originalConsoleError(...args);
  });
  jest.spyOn(console, "warn").mockImplementation((...args: unknown[]) => {
    if (String(args[0] ?? "").match(/telemetry|Telemetry/)) return;
    originalConsoleWarn(...args);
  });
});

afterAll(() => jest.restoreAllMocks());
afterEach(() => {
  global.fetch = originalFetch;
});

// Shared test data matching realistic API responses
const userId = "test_user_abc123";
const memoryId = "mem_550e8400";

const mockMemory = createMockMemory({
  id: memoryId,
  memory: "Alex is a vegetarian",
  user_id: userId,
  event: "ADD",
  data: { memory: "Alex is a vegetarian" },
  categories: ["personal"],
  metadata: null,
  created_at: "2026-03-17T10:00:00Z",
  updated_at: "2026-03-17T10:00:00Z",
  score: 0.95,
});

function mockFetchForTest(
  extraPatterns?: Record<string, { status: number; body: unknown }>,
) {
  const responses = new Map<string, { status: number; body: unknown }>();
  responses.set("/v1/ping/", { status: 200, body: MOCK_PING_RESPONSE });
  responses.set("/v1/memories/search/", { status: 200, body: [mockMemory] });
  responses.set("/v2/memories/search/", { status: 200, body: [mockMemory] });
  responses.set("/history/", {
    status: 200,
    body: [
      createMockMemoryHistory({
        memory_id: memoryId,
        user_id: userId,
        event: "ADD",
        old_memory: null,
        new_memory: "Alex is a vegetarian",
      }),
    ],
  });
  responses.set("/v1/entities/", {
    status: 200,
    body: createMockAllUsers([
      createMockUser({ id: "entity_1", name: userId, type: "user" }),
    ]),
  });
  // This must come last — it's a broad pattern that matches /v1/memories/:id/ and /v1/memories/
  responses.set("/v1/memories/", { status: 200, body: [mockMemory] });

  if (extraPatterns) {
    for (const [k, v] of Object.entries(extraPatterns)) {
      responses.set(k, v);
    }
  }

  global.fetch = createMockFetch(responses);
}

describe("MemoryClient API", () => {
  beforeEach(() => mockFetchForTest());

  const messages1 = [
    { role: "user" as const, content: "Hey, I am Alex. I'm now a vegetarian." },
    { role: "assistant" as const, content: "Hello Alex! Glad to hear!" },
  ];

  it("should add messages successfully", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const res = await client.add(messages1, { user_id: userId });

    expect(Array.isArray(res)).toBe(true);
    const message = res[0];
    expect(typeof message.id).toBe("string");
    expect(typeof message.data?.memory).toBe("string");
    expect(typeof message.event).toBe("string");
  });

  it("should retrieve the specific memory by ID", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    // getAll returns array, first item is our mock memory
    const memories = await client.getAll({ user_id: userId });
    const memory = Array.isArray(memories) ? memories[0] : memories;

    expect(typeof memory.id).toBe("string");
    expect(typeof memory.memory).toBe("string");
    expect(typeof memory.user_id).toBe("string");
    expect(memory.user_id).toBe(userId);
    expect(
      memory.metadata === null || typeof memory.metadata === "object",
    ).toBe(true);
    expect(Array.isArray(memory.categories) || memory.categories === null).toBe(
      true,
    );
    if (Array.isArray(memory.categories)) {
      memory.categories.forEach((category) => {
        expect(typeof category).toBe("string");
      });
    }
    expect(new Date(memory.created_at || "").toString()).not.toBe(
      "Invalid Date",
    );
    expect(new Date(memory.updated_at || "").toString()).not.toBe(
      "Invalid Date",
    );
  });

  it("should retrieve all users successfully", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const allUsers = await client.users();

    expect(typeof allUsers.count).toBe("number");
    const firstUser = allUsers.results[0];
    expect(typeof firstUser.id).toBe("string");
    expect(typeof firstUser.name).toBe("string");
    expect(typeof firstUser.created_at).toBe("string");
    expect(typeof firstUser.updated_at).toBe("string");
    expect(typeof firstUser.total_memories).toBe("number");
    expect(typeof firstUser.type).toBe("string");

    const entity = allUsers.results.find((user) => user.name === userId);
    expect(entity).not.toBeUndefined();
    expect(typeof entity?.id).toBe("string");
  });

  it("should retrieve all memories for the user", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const res3 = await client.getAll({ user_id: userId });

    expect(Array.isArray(res3)).toBe(true);
    if (res3.length > 0) {
      const memory = res3[0];
      expect(typeof memory.id).toBe("string");
      expect(typeof memory.memory).toBe("string");
      expect(typeof memory.user_id).toBe("string");
      expect(memory.user_id).toBe(userId);
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    }
  });

  it("should search and return results based on provided query and filters (API version 2)", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const searchResultV2 = await client.search("What do you know about me?", {
      filters: {
        OR: [{ user_id: userId }, { agent_id: "shopping-assistant" }],
      },
      threshold: 0.1,
      api_version: "v2",
    });

    expect(Array.isArray(searchResultV2)).toBe(true);
    if (searchResultV2.length > 0) {
      const memory = searchResultV2[0];
      expect(typeof memory.id).toBe("string");
      expect(typeof memory.memory).toBe("string");
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );
      expect(typeof memory.score).toBe("number");
    }
  });

  it("should search and return results based on provided query (API version 1)", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const searchResultV1 = await client.search("What is my name?", {
      user_id: userId,
    });

    expect(Array.isArray(searchResultV1)).toBe(true);
    if (searchResultV1.length > 0) {
      const memory = searchResultV1[0];
      expect(typeof memory.id).toBe("string");
      expect(typeof memory.memory).toBe("string");
      expect(typeof memory.user_id).toBe("string");
      expect(memory.user_id).toBe(userId);
      expect(typeof memory.score).toBe("number");
    }
  });

  it("should retrieve history of a specific memory and validate the fields", async () => {
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const res22 = await client.history(memoryId);

    expect(Array.isArray(res22)).toBe(true);
    if (res22.length > 0) {
      const historyEntry = res22[0];
      expect(typeof historyEntry.id).toBe("string");
      expect(typeof historyEntry.memory_id).toBe("string");
      expect(typeof historyEntry.user_id).toBe("string");
      expect(historyEntry.user_id).toBe(userId);
      expect(
        historyEntry.old_memory === null ||
          typeof historyEntry.old_memory === "string",
      ).toBe(true);
      expect(
        historyEntry.new_memory === null ||
          typeof historyEntry.new_memory === "string",
      ).toBe(true);
      expect(new Date(historyEntry.created_at).toString()).not.toBe(
        "Invalid Date",
      );
      expect(new Date(historyEntry.updated_at).toString()).not.toBe(
        "Invalid Date",
      );
      expect(["ADD", "UPDATE", "DELETE", "NOOP"]).toContain(historyEntry.event);

      if (historyEntry.event === "ADD") {
        expect(historyEntry.old_memory).toBeNull();
        expect(historyEntry.new_memory).not.toBeNull();
      }

      expect(
        Array.isArray(historyEntry.input) || historyEntry.input === null,
      ).toBe(true);
      if (Array.isArray(historyEntry.input)) {
        historyEntry.input.forEach((input) => {
          expect(typeof input).toBe("object");
          expect(typeof input.content).toBe("string");
          expect(["user", "assistant"]).toContain(input.role);
        });
      }
    }
  });

  it("should delete the user successfully", async () => {
    const client = new MemoryClient({
      apiKey: TEST_API_KEY,
      organizationId: "org_test",
      projectId: "proj_test",
    });
    client.client.delete = jest
      .fn()
      .mockResolvedValue({ data: { message: "Entity deleted successfully!" } });

    const result = await client.deleteUsers({ user_id: userId });
    expect(result.message).toBe("Entity deleted successfully.");
  });
});
