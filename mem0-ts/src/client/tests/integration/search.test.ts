/**
 * Integration tests: Search and history operations.
 *
 * Tests search v1, search v2, and memory history against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest search.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  seedTestMemories,
  cleanupTestUser,
  waitForSearchResults,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-search-${randomUUID()}`;

describeIntegration("MemoryClient Integration — Search & History", () => {
  let client: MemoryClient;
  let cleanup: () => void;
  let memoryIds: string[] = [];

  beforeAll(async () => {
    cleanup = suppressTelemetryNoise();
    client = createTestClient();
    memoryIds = await seedTestMemories(client, TEST_USER_ID);
  });

  afterAll(async () => {
    await cleanupTestUser(client, TEST_USER_ID);
    cleanup();
  });

  // ─── Search v1 ────────────────────────────────────────────
  describe("search v1", () => {
    test("searches memories by user_id and returns results with scores", async () => {
      // Search index may lag behind listing index — poll until ready
      const results = await waitForSearchResults(
        client,
        "What is my favorite color?",
        { user_id: TEST_USER_ID },
      );

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      const first = results[0];
      expect(typeof first.id).toBe("string");
      expect(typeof first.memory).toBe("string");
      expect(typeof first.score).toBe("number");
      expect(first.score).toBeGreaterThan(0);
    });
  });

  // ─── Search v2 ────────────────────────────────────────────
  describe("search v2", () => {
    test("searches with OR filters and returns results", async () => {
      const results = await waitForSearchResults(
        client,
        "What do you know about me?",
        {
          filters: { OR: [{ user_id: TEST_USER_ID }] },
          api_version: "v2",
        },
      );

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      const first = results[0];
      expect(typeof first.id).toBe("string");
      expect(typeof first.memory).toBe("string");
      expect(typeof first.score).toBe("number");
    });
  });

  // ─── History ──────────────────────────────────────────────
  describe("memory history", () => {
    test("returns history with at least an ADD event", async () => {
      const memoryId = memoryIds[0];
      const history = await client.history(memoryId);

      expect(Array.isArray(history)).toBe(true);
      expect(history.length).toBeGreaterThanOrEqual(1);

      const entry = history[0];
      expect(typeof entry.id).toBe("string");
      expect(typeof entry.memory_id).toBe("string");
      expect(["ADD", "UPDATE", "DELETE", "NOOP"]).toContain(entry.event);
      expect(new Date(entry.created_at).toString()).not.toBe("Invalid Date");
      expect(new Date(entry.updated_at).toString()).not.toBe("Invalid Date");
      expect(
        entry.new_memory === null || typeof entry.new_memory === "string",
      ).toBe(true);
      expect(
        entry.old_memory === null || typeof entry.old_memory === "string",
      ).toBe(true);

      const events = history.map((h) => h.event);
      expect(events).toContain("ADD");
    });
  });
});
