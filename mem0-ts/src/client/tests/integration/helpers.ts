/**
 * Shared helpers for MemoryClient real integration tests.
 *
 * Provides environment gating, client factory, polling helpers,
 * and console suppression for telemetry noise.
 *
 * All helpers use only the SDK's public API — no internal method access.
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
 * Returns an initialized client ready for immediate use.
 */
export async function createTestClient(): Promise<MemoryClient> {
  const client = new MemoryClient({ apiKey: API_KEY! });
  await client.ping();
  return client;
}

/**
 * Retry an async SDK call on transient errors (NetworkError, RateLimitError).
 * Use this to wrap any SDK call that may flake in CI.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 2,
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      const isTransient =
        error instanceof NetworkError || error instanceof RateLimitError;
      if (isTransient && attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, 3_000 * attempt));
        continue;
      }
      throw error;
    }
  }
  throw new Error("withRetry: unreachable");
}

/**
 * Poll getAll until memories appear for a user.
 * The Mem0 API processes memories asynchronously — after add()
 * we need to wait for them to be available.
 *
 * Polls every 15 seconds with a maximum of 4 retries to avoid
 * hitting rate limits. Throws if results aren't available after
 * all retries.
 */
export async function waitForMemories(
  client: MemoryClient,
  userId: string,
  minCount: number,
  maxRetries = 4,
): Promise<Memory[]> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const response = await withRetry(() =>
      client.getAll({ filters: { user_id: userId } }),
    );
    const memories = response.results ?? [];
    if (memories.length >= minCount) {
      return memories;
    }
    if (attempt < maxRetries) {
      await new Promise((r) => setTimeout(r, 15_000));
    }
  }
  throw new Error(
    `waitForMemories: expected at least ${minCount} memories for user "${userId}" but did not get them after ${maxRetries} attempts`,
  );
}

/**
 * Poll search until results appear. Only used by search tests —
 * other test files should NOT call this to avoid wasting API credits.
 *
 * Polls every 15 seconds with a maximum of 4 retries. Throws if
 * no results are found after all retries.
 */
export async function waitForSearchResults(
  client: MemoryClient,
  query: string,
  options: Record<string, any>,
  maxRetries = 4,
): Promise<Memory[]> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const response = await withRetry(() => client.search(query, options));
    const results = response?.results ?? [];
    if (results.length > 0) {
      return results;
    }
    if (attempt < maxRetries) {
      await new Promise((r) => setTimeout(r, 15_000));
    }
  }
  throw new Error(
    `waitForSearchResults: no results for query "${query}" after ${maxRetries} attempts`,
  );
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
  await withRetry(() =>
    client.add(
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
      { userId },
    ),
  );

  await withRetry(() =>
    client.add(
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
      { userId },
    ),
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
    await client.deleteAll({ userId });
  } catch {
    // ignore
  }
  try {
    await client.deleteUsers({ userId });
  } catch {
    // ignore
  }
}

/**
 * Full project wipe — deletes all memories and all entities.
 * Equivalent to Python SDK's:
 *   client.delete_all(user_id="*", agent_id="*", app_id="*", run_id="*")
 *
 * Used as cleanup before and after integration test runs so tests
 * start from a clean slate and don't leave data behind.
 */
export async function fullProjectCleanup(client: MemoryClient): Promise<void> {
  // Delete all memories — all four filters set explicitly
  try {
    await client.deleteAll({
      userId: "*",
      agentId: "*",
      appId: "*",
      runId: "*",
    });
  } catch {
    // ignore — may 404 if no data exists
  }

  // Delete all entities (users, agents, apps, runs)
  try {
    await client.deleteUsers();
  } catch {
    // ignore — may throw "No entities to delete"
  }
}
