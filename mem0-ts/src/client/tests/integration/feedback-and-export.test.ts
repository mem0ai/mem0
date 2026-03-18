/**
 * Integration tests: Feedback and memory export.
 *
 * Tests feedback submission and the export lifecycle
 * (create → retrieve) against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest feedback-and-export.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { Feedback } from "../../mem0.types";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  seedTestMemories,
  cleanupTestUser,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-fb-export-${randomUUID()}`;

describeIntegration("MemoryClient Integration — Feedback & Export", () => {
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

  // ─── Feedback ─────────────────────────────────────────────
  // Note: client.feedback() is deprecated and doesn't send org_id/project_id,
  // so we call _fetchWithErrorHandling directly to test the API endpoint.
  describe("feedback", () => {
    test("submits positive feedback on a memory", async () => {
      const memoryId = memoryIds[0];
      expect(memoryId).toBeDefined();

      const payload = {
        memory_id: memoryId,
        feedback: Feedback.POSITIVE,
        org_id: String(client.organizationId),
        project_id: String(client.projectId),
      };

      const result = await (client as any)._fetchWithErrorHandling(
        `${client.host}/v1/feedback/`,
        {
          method: "POST",
          headers: client.headers,
          body: JSON.stringify(payload),
        },
      );

      expect(result).toBeDefined();
    });
  });

  // ─── Export ───────────────────────────────────────────────
  describe("memory export", () => {
    let exportId: string | undefined;

    test("creates a memory export", async () => {
      const result = await client.createMemoryExport({
        filters: { AND: [{ user_id: TEST_USER_ID }] },
        schema: { memory: "string", user_id: "string" },
      });

      expect(result).toBeDefined();
      expect(
        typeof result.id === "string" || typeof result.message === "string",
      ).toBe(true);

      exportId = result.id;
    });

    test("retrieves a memory export", async () => {
      if (!exportId) return;

      const result = await client.getMemoryExport({
        memory_export_id: exportId,
      });

      expect(result).toBeDefined();
    });
  });
});
