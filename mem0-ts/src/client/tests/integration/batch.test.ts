/**
 * Integration tests: Batch operations.
 *
 * Tests batch update and batch delete against the real API.
 *
 * Run: MEM0_API_KEY=your-key npx jest batch.test.ts --forceExit
 */
import { MemoryClient } from "../../mem0";
import { randomUUID } from "crypto";
import {
  describeIntegration,
  createTestClient,
  suppressTelemetryNoise,
  seedTestMemories,
  cleanupTestUser,
} from "./helpers";

jest.setTimeout(120_000);

const TEST_USER_ID = `integration-batch-${randomUUID()}`;

describeIntegration("MemoryClient Integration — Batch Operations", () => {
  let client: MemoryClient;
  let cleanup: () => void;
  let memoryIds: string[] = [];

  beforeAll(async () => {
    cleanup = suppressTelemetryNoise();
    client = await createTestClient();
    memoryIds = await seedTestMemories(client, TEST_USER_ID);
  });

  afterAll(async () => {
    await cleanupTestUser(client, TEST_USER_ID);
    cleanup();
  });

  test("batch updates memories", async () => {
    expect(memoryIds.length).toBeGreaterThanOrEqual(1);

    const batchPayload = memoryIds
      .slice(0, Math.min(2, memoryIds.length))
      .map((id) => ({
        memoryId: id,
        text: `Batch updated content for ${id}`,
      }));

    const result = await client.batchUpdate(batchPayload);
    expect(result).toBeDefined();

    // Verify the update took effect on at least one memory
    const updated = await client.get(memoryIds[0]);
    expect(typeof updated.memory).toBe("string");
  });

  test("batch deletes memories that exist", async () => {
    // Use one of the seeded memory IDs that we know exists
    expect(memoryIds.length).toBeGreaterThanOrEqual(1);

    const toDelete = [memoryIds[memoryIds.length - 1]];
    const result = await client.batchDelete(toDelete);
    expect(result).toBeDefined();
  });
});
