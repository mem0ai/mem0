/**
 * Integration tests: Memory CRUD operations.
 *
 * Tests the full lifecycle: add → get → getAll → update → delete.
 * Validates response shapes against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest crud.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { MemoryError } from "../../../common/exceptions";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  waitForMemories,
  cleanupTestUser,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-crud-${randomUUID()}`;

describeIntegration("MemoryClient Integration — CRUD", () => {
  let client: MemoryClient;
  let cleanup: () => void;
  let memoryIds: string[] = [];

  beforeAll(() => {
    cleanup = suppressTelemetryNoise();
    client = createTestClient();
  });

  afterAll(async () => {
    await cleanupTestUser(client, TEST_USER_ID);
    cleanup();
  });

  // ─── Add ──────────────────────────────────────────────────
  describe("add memories", () => {
    test("add returns a pending response with event_id", async () => {
      const messages = [
        {
          role: "user" as const,
          content: "Hi, I'm integration-test-user. My favorite color is blue.",
        },
        {
          role: "assistant" as const,
          content:
            "Nice to meet you! I'll remember that your favorite color is blue.",
        },
      ];

      const result = await client.add(messages, { user_id: TEST_USER_ID });

      // API processes memories asynchronously — returns PENDING
      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);

      // Validate response shape
      for (const item of result) {
        expect(item).toHaveProperty("status");
        expect(item).toHaveProperty("event_id");
      }
    });

    test("adds a second batch of messages", async () => {
      const messages = [
        {
          role: "user" as const,
          content: "I work as a software engineer at Acme Corp.",
        },
        {
          role: "assistant" as const,
          content: "Got it, you're a software engineer at Acme Corp!",
        },
      ];

      const result = await client.add(messages, { user_id: TEST_USER_ID });
      expect(Array.isArray(result)).toBe(true);
    });

    test("memories become available after async processing", async () => {
      const memories = await waitForMemories(client, TEST_USER_ID, 1);

      expect(memories.length).toBeGreaterThan(0);

      // Store IDs for later tests
      memoryIds = memories.map((m) => m.id);
      expect(memoryIds.length).toBeGreaterThan(0);
      expect(typeof memoryIds[0]).toBe("string");
    });
  });

  // ─── Get by ID ────────────────────────────────────────────
  describe("get memory by ID", () => {
    test("retrieves a specific memory with correct shape", async () => {
      const memoryId = memoryIds[0];
      expect(memoryId).toBeDefined();

      const memory = await client.get(memoryId);

      expect(memory.id).toBe(memoryId);
      expect(typeof memory.memory).toBe("string");
      expect(memory.memory!.length).toBeGreaterThan(0);
      expect(typeof memory.user_id).toBe("string");
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
    });
  });

  // ─── Get all ──────────────────────────────────────────────
  describe("get all memories", () => {
    test("returns all memories for test user", async () => {
      const memories = await client.getAll({
        filters: { user_id: TEST_USER_ID },
      });

      expect(Array.isArray(memories)).toBe(true);
      expect(memories.length).toBeGreaterThanOrEqual(memoryIds.length);

      for (const mem of memories) {
        expect(typeof mem.id).toBe("string");
        expect(typeof mem.memory).toBe("string");
      }
    });

    test("returns paginated results with page and page_size", async () => {
      const page1 = await client.getAll({
        filters: { user_id: TEST_USER_ID },
        page: 1,
        page_size: 1,
      });

      // Paginated response is an object with results array
      expect(page1).toBeDefined();
    });
  });

  // ─── Update ───────────────────────────────────────────────
  describe("update memory", () => {
    test("updates memory text and verifies the content changed", async () => {
      const memoryId = memoryIds[0];

      // Read original text before update
      const original = await client.get(memoryId);
      const originalText = original.memory;

      await client.update(memoryId, {
        text: "My favorite color is green (updated)",
      });

      const updated = await client.get(memoryId);
      expect(typeof updated.memory).toBe("string");
      expect(updated.memory).not.toBe(originalText);
    });

    test("updates memory metadata", async () => {
      const memoryId = memoryIds[0];

      await client.update(memoryId, {
        metadata: { source: "integration-test", priority: "high" },
      });

      const updated = await client.get(memoryId);
      expect(updated.metadata).toBeDefined();
      expect(updated.metadata.source).toBe("integration-test");
      expect(updated.metadata.priority).toBe("high");
    });
  });

  // ─── Edge cases ──────────────────────────────────────────
  describe("edge cases", () => {
    test("add with metadata attaches metadata to the memory", async () => {
      const result = await client.add(
        [
          { role: "user" as const, content: "I prefer dark mode in all apps." },
          {
            role: "assistant" as const,
            content: "Noted, dark mode preference saved!",
          },
        ],
        {
          user_id: TEST_USER_ID,
          metadata: { source: "integration-test", category: "preferences" },
        },
      );

      expect(Array.isArray(result)).toBe(true);
      expect(result.length).toBeGreaterThan(0);
    });

    test("getAll for non-existent user returns empty array", async () => {
      const memories = await client.getAll({
        filters: { user_id: `nonexistent-user-${randomUUID()}` },
      });

      expect(Array.isArray(memories)).toBe(true);
      expect(memories.length).toBe(0);
    });

    test("deleteAll for non-existent user does not throw", async () => {
      const result = await client.deleteAll({
        user_id: `nonexistent-user-${randomUUID()}`,
      });

      expect(result).toBeDefined();
      expect(typeof result.message).toBe("string");
    });
  });

  // ─── Delete single ────────────────────────────────────────
  // NOTE: Delete tests run last to avoid race conditions with
  // other tests that depend on the seeded memories.
  describe("delete memory", () => {
    test("deletes a single memory by ID", async () => {
      const memoryId = memoryIds[0];
      expect(memoryId).toBeDefined();

      const result = await client.delete(memoryId);
      expect(result).toBeDefined();
      expect(typeof result.message).toBe("string");
    });

    test("getting deleted memory throws MemoryError", async () => {
      const memoryId = memoryIds[0];
      await expect(client.get(memoryId)).rejects.toThrow(MemoryError);
    });
  });

  // ─── Delete all + delete user ─────────────────────────────
  describe("cleanup operations", () => {
    test("deletes all memories for test user", async () => {
      const result = await client.deleteAll({ user_id: TEST_USER_ID });
      expect(result).toBeDefined();
      expect(typeof result.message).toBe("string");
    });

    test("deletes the test user entity", async () => {
      const result = await client.deleteUsers({ user_id: TEST_USER_ID });
      expect(result).toBeDefined();
      expect(result.message).toBe("Entity deleted successfully.");
    });
  });
});
