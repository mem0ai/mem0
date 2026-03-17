/**
 * MemoryClient E2E integration tests.
 *
 * These tests exercise realistic usage patterns with mock HTTP responses.
 * Skipped by default — run with MEM0_RUN_E2E=1 to enable.
 *
 * Run: MEM0_RUN_E2E=1 npx jest memoryClient.e2e.test.ts
 */
import { MemoryClient } from "../mem0";
import type {
  Memory,
  AllUsers,
  MemoryHistory,
  User,
  Messages,
} from "../mem0.types";
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

const describeOrSkip = process.env.MEM0_RUN_E2E ? describe : describe.skip;

describeOrSkip("MemoryClient API (E2E)", () => {
  beforeEach(() => mockFetchForTest());

  const messages1 = [
    { role: "user" as const, content: "Hey, I am Alex. I'm now a vegetarian." },
    { role: "assistant" as const, content: "Hello Alex! Glad to hear!" },
  ];

  describe("add messages", () => {
    let res: Memory[];

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      res = await client.add(messages1, { user_id: userId });
    });

    test("returns an array", () => {
      expect(Array.isArray(res)).toBe(true);
    });

    test("first message has a string id", () => {
      expect(typeof res[0].id).toBe("string");
    });

    test("first message has a string data.memory", () => {
      expect(typeof res[0].data?.memory).toBe("string");
    });

    test("first message has a string event", () => {
      expect(typeof res[0].event).toBe("string");
    });
  });

  describe("retrieve specific memory by ID", () => {
    let memory: Memory;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      const memories = await client.getAll({ user_id: userId });
      memory = Array.isArray(memories) ? memories[0] : memories;
    });

    test("returns string id", () => {
      expect(typeof memory.id).toBe("string");
    });

    test("returns string memory content", () => {
      expect(typeof memory.memory).toBe("string");
    });

    test("returns string user_id", () => {
      expect(typeof memory.user_id).toBe("string");
    });

    test("user_id matches the requested userId", () => {
      expect(memory.user_id).toBe(userId);
    });

    test("metadata is null or an object", () => {
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);
    });

    test("categories is an array or null", () => {
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
    });

    test("each category is a string", () => {
      if (Array.isArray(memory.categories)) {
        expect(
          memory.categories.every((c: string) => typeof c === "string"),
        ).toBe(true);
      }
    });

    test("created_at is a valid date", () => {
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    });

    test("updated_at is a valid date", () => {
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    });
  });

  describe("retrieve all users", () => {
    let allUsers: AllUsers;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      allUsers = await client.users();
    });

    test("count is a number", () => {
      expect(typeof allUsers.count).toBe("number");
    });

    test("first user has a string id", () => {
      expect(typeof allUsers.results[0].id).toBe("string");
    });

    test("first user has a string name", () => {
      expect(typeof allUsers.results[0].name).toBe("string");
    });

    test("first user has a string created_at", () => {
      expect(typeof allUsers.results[0].created_at).toBe("string");
    });

    test("first user has a string updated_at", () => {
      expect(typeof allUsers.results[0].updated_at).toBe("string");
    });

    test("first user has a number total_memories", () => {
      expect(typeof allUsers.results[0].total_memories).toBe("number");
    });

    test("first user has a string type", () => {
      expect(typeof allUsers.results[0].type).toBe("string");
    });

    test("results contain an entity matching userId", () => {
      const entity = allUsers.results.find(
        (user: User) => user.name === userId,
      );
      expect(entity).not.toBeUndefined();
    });

    test("matched entity has a string id", () => {
      const entity = allUsers.results.find(
        (user: User) => user.name === userId,
      );
      expect(typeof entity?.id).toBe("string");
    });
  });

  describe("retrieve all memories for the user", () => {
    let memories: Memory[];
    let memory: Memory;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      memories = await client.getAll({ user_id: userId });
      memory = memories[0];
    });

    test("returns an array", () => {
      expect(Array.isArray(memories)).toBe(true);
    });

    test("first memory has a string id", () => {
      expect(typeof memory.id).toBe("string");
    });

    test("first memory has a string memory content", () => {
      expect(typeof memory.memory).toBe("string");
    });

    test("first memory has a string user_id", () => {
      expect(typeof memory.user_id).toBe("string");
    });

    test("first memory user_id matches the requested userId", () => {
      expect(memory.user_id).toBe(userId);
    });

    test("first memory metadata is null or an object", () => {
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);
    });

    test("first memory categories is an array or null", () => {
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
    });

    test("first memory created_at is a valid date", () => {
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    });

    test("first memory updated_at is a valid date", () => {
      expect(new Date(memory.updated_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    });
  });

  describe("search with API version 2", () => {
    let results: Memory[];
    let memory: Memory;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      results = await client.search("What do you know about me?", {
        filters: {
          OR: [{ user_id: userId }, { agent_id: "shopping-assistant" }],
        },
        threshold: 0.1,
        api_version: "v2",
      });
      memory = results[0];
    });

    test("returns an array", () => {
      expect(Array.isArray(results)).toBe(true);
    });

    test("first result has a string id", () => {
      expect(typeof memory.id).toBe("string");
    });

    test("first result has a string memory content", () => {
      expect(typeof memory.memory).toBe("string");
    });

    test("first result metadata is null or an object", () => {
      expect(
        memory.metadata === null || typeof memory.metadata === "object",
      ).toBe(true);
    });

    test("first result categories is an array or null", () => {
      expect(
        Array.isArray(memory.categories) || memory.categories === null,
      ).toBe(true);
    });

    test("first result created_at is a valid date", () => {
      expect(new Date(memory.created_at || "").toString()).not.toBe(
        "Invalid Date",
      );
    });

    test("first result has a number score", () => {
      expect(typeof memory.score).toBe("number");
    });
  });

  describe("search with API version 1", () => {
    let results: Memory[];
    let memory: Memory;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      results = await client.search("What is my name?", {
        user_id: userId,
      });
      memory = results[0];
    });

    test("returns an array", () => {
      expect(Array.isArray(results)).toBe(true);
    });

    test("first result has a string id", () => {
      expect(typeof memory.id).toBe("string");
    });

    test("first result has a string memory content", () => {
      expect(typeof memory.memory).toBe("string");
    });

    test("first result has a string user_id", () => {
      expect(typeof memory.user_id).toBe("string");
    });

    test("first result user_id matches the requested userId", () => {
      expect(memory.user_id).toBe(userId);
    });

    test("first result has a number score", () => {
      expect(typeof memory.score).toBe("number");
    });
  });

  describe("retrieve history of a specific memory", () => {
    let history: MemoryHistory[];
    let entry: MemoryHistory;

    beforeEach(async () => {
      const client = new MemoryClient({ apiKey: TEST_API_KEY });
      history = await client.history(memoryId);
      entry = history[0];
    });

    test("returns an array", () => {
      expect(Array.isArray(history)).toBe(true);
    });

    test("first entry has a string id", () => {
      expect(typeof entry.id).toBe("string");
    });

    test("first entry has a string memory_id", () => {
      expect(typeof entry.memory_id).toBe("string");
    });

    test("first entry has a string user_id", () => {
      expect(typeof entry.user_id).toBe("string");
    });

    test("first entry user_id matches the requested userId", () => {
      expect(entry.user_id).toBe(userId);
    });

    test("old_memory is null or a string", () => {
      expect(
        entry.old_memory === null || typeof entry.old_memory === "string",
      ).toBe(true);
    });

    test("new_memory is null or a string", () => {
      expect(
        entry.new_memory === null || typeof entry.new_memory === "string",
      ).toBe(true);
    });

    test("created_at is a valid date", () => {
      expect(new Date(entry.created_at).toString()).not.toBe("Invalid Date");
    });

    test("updated_at is a valid date", () => {
      expect(new Date(entry.updated_at).toString()).not.toBe("Invalid Date");
    });

    test("event is one of ADD, UPDATE, DELETE, NOOP", () => {
      expect(["ADD", "UPDATE", "DELETE", "NOOP"]).toContain(entry.event);
    });

    test("ADD event has null old_memory", () => {
      expect(entry.old_memory).toBeNull();
    });

    test("ADD event has non-null new_memory", () => {
      expect(entry.new_memory).not.toBeNull();
    });

    test("input is an array or null", () => {
      expect(Array.isArray(entry.input) || entry.input === null).toBe(true);
    });

    test("each input item is an object", () => {
      if (Array.isArray(entry.input)) {
        expect(entry.input.every((i: Messages) => typeof i === "object")).toBe(
          true,
        );
      }
    });

    test("each input item has a string content", () => {
      if (Array.isArray(entry.input)) {
        expect(
          entry.input.every((i: Messages) => typeof i.content === "string"),
        ).toBe(true);
      }
    });

    test("each input item has a valid role", () => {
      if (Array.isArray(entry.input)) {
        expect(
          entry.input.every((i: Messages) =>
            ["user", "assistant"].includes(i.role),
          ),
        ).toBe(true);
      }
    });
  });

  describe("delete user", () => {
    test("returns success message", async () => {
      const client = new MemoryClient({
        apiKey: TEST_API_KEY,
        organizationId: "org_test",
        projectId: "proj_test",
      });
      client.client.delete = jest.fn().mockResolvedValue({
        data: { message: "Entity deleted successfully!" },
      });

      const result = await client.deleteUsers({ user_id: userId });
      expect(result.message).toBe("Entity deleted successfully.");
    });
  });
});
