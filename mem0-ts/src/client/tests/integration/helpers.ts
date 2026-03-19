/**
 * Shared helpers for MemoryClient real integration tests.
 *
 * Provides environment gating, client factory, polling helpers,
 * and console suppression for telemetry noise.
 */
import { MemoryClient } from "../../mem0";
import type { Memory } from "../../mem0.types";

// ─── Environment gate ────────────────────────────────────
export const API_KEY = process.env.MEM0_API_KEY;
export const describeIntegration = API_KEY ? describe : describe.skip;

/**
 * Create a MemoryClient with the real API key.
 * Call this inside beforeAll — not at module scope — so it only
 * runs when the suite is not skipped.
 */
export function createTestClient(): MemoryClient {
  return new MemoryClient({ apiKey: API_KEY! });
}

/**
 * Poll getAll until memories appear for a user.
 * The Mem0 API processes memories asynchronously — after add()
 * we need to wait for them to be available.
 */
export async function waitForMemories(
  client: MemoryClient,
  userId: string,
  minCount: number,
  maxWaitMs = 30_000,
): Promise<Memory[]> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const memories = await client.getAll({ user_id: userId });
    if (Array.isArray(memories) && memories.length >= minCount) {
      return memories;
    }
    await new Promise((r) => setTimeout(r, 2_000));
  }
  return await client.getAll({ user_id: userId });
}

/**
 * Suppress telemetry console noise during tests.
 * Returns a cleanup function to call in afterAll.
 */
export function suppressTelemetryNoise(): () => void {
  const originalError = console.error;
  const originalWarn = console.warn;

  jest.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    if (
      String(args[0] ?? "").match(
        /Telemetry|Failed to initialize|Failed to capture/,
      )
    )
      return;
    originalError(...args);
  });
  jest.spyOn(console, "warn").mockImplementation((...args: unknown[]) => {
    if (String(args[0] ?? "").match(/telemetry|Telemetry/)) return;
    originalWarn(...args);
  });

  return () => jest.restoreAllMocks();
}

/**
 * Add test memories and wait for them to be processed.
 * Returns the memory IDs once available.
 */
export async function seedTestMemories(
  client: MemoryClient,
  userId: string,
): Promise<string[]> {
  await client.add(
    [
      {
        role: "user" as const,
        content: "Hi, I'm integration-test-user. My favorite color is blue.",
      },
      {
        role: "assistant" as const,
        content:
          "Nice to meet you! I'll remember that your favorite color is blue.",
      },
    ],
    { user_id: userId },
  );

  await client.add(
    [
      {
        role: "user" as const,
        content: "I work as a software engineer at Acme Corp.",
      },
      {
        role: "assistant" as const,
        content: "Got it, you're a software engineer at Acme Corp!",
      },
    ],
    { user_id: userId },
  );

  // Wait for async processing (listing index)
  const memories = await waitForMemories(client, userId, 1);

  // Also wait for search index — it can lag behind getAll under load (e.g. CI)
  const start = Date.now();
  while (Date.now() - start < 60_000) {
    const results = await client.search("favorite color", { user_id: userId });
    if (Array.isArray(results) && results.length > 0) break;
    await new Promise((r) => setTimeout(r, 3_000));
  }

  return memories.map((m) => m.id);
}

/**
 * Clean up all test data for a user. Best-effort — ignores errors.
 */
export async function cleanupTestUser(
  client: MemoryClient,
  userId: string,
): Promise<void> {
  try {
    await client.deleteAll({ user_id: userId });
  } catch {
    // ignore
  }
  try {
    await client.deleteUsers({ user_id: userId });
  } catch {
    // ignore
  }
}
