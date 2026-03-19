/**
 * Shared helpers for MemoryClient real integration tests.
 *
 * Provides environment gating, client factory, polling helpers,
 * and console suppression for telemetry noise.
 *
 * API credit budget: these helpers are designed to minimize API calls.
 * Each CI run should use ~40 calls total across all test files.
 */
import { MemoryClient } from "../../mem0";
import type { Memory } from "../../mem0.types";
import { NetworkError, RateLimitError } from "../../../common/exceptions";

// ─── Environment gate ────────────────────────────────────
export const API_KEY = process.env.MEM0_API_KEY;
export const describeIntegration = API_KEY ? describe : describe.skip;

/**
 * Create a MemoryClient with the real API key.
 * Call this inside beforeAll — not at module scope — so it only
 * runs when the suite is not skipped.
 *
 * The returned client retries transient errors (502, 503, 504, 429)
 * with backoff so CI runs are not flaky.
 */
export function createTestClient(): MemoryClient {
  const client = new MemoryClient({ apiKey: API_KEY! });

  const originalFetch = (client as any)._fetchWithErrorHandling.bind(client);
  (client as any)._fetchWithErrorHandling = async (
    url: string,
    options: any,
  ) => {
    const MAX_RETRIES = 2;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      try {
        return await originalFetch(url, options);
      } catch (error: any) {
        const isTransient =
          error instanceof NetworkError || error instanceof RateLimitError;
        if (isTransient && attempt < MAX_RETRIES) {
          await new Promise((r) => setTimeout(r, 3_000 * attempt));
          continue;
        }
        throw error;
      }
    }
  };

  return client;
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
 * Poll search until results appear. Only used by search tests —
 * other test files should NOT call this to avoid wasting API credits.
 */
export async function waitForSearchResults(
  client: MemoryClient,
  query: string,
  options: Record<string, any>,
  maxWaitMs = 30_000,
): Promise<Memory[]> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const results = await client.search(query, options);
    if (Array.isArray(results) && results.length > 0) {
      return results;
    }
    await new Promise((r) => setTimeout(r, 3_000));
  }
  return await client.search(query, options);
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
 * Returns the memory IDs once available via getAll.
 *
 * NOTE: This only waits for the listing index. If your test needs
 * search results, call waitForSearchResults() separately.
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

  const memories = await waitForMemories(client, userId, 1);
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
