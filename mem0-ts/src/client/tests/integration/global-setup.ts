/**
 * Jest global setup for integration tests.
 *
 * Runs a full project cleanup before any integration test starts,
 * then waits 10 seconds for the async cleanup to propagate.
 */

export default async function globalSetup() {
  const pkg = require("../../../../package.json");
  (globalThis as any).__MEM0_SDK_VERSION__ = pkg.version;

  const apiKey = process.env.MEM0_API_KEY;
  if (!apiKey) return; // skip if no key — tests will be skipped too

  const { MemoryClient } = await import("../../mem0");
  const client = new MemoryClient({ apiKey });
  await client.ping();

  console.log("[integration] Running pre-test cleanup...");

  // Full project wipe — all four filters set explicitly
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

  try {
    await client.deleteUsers();
  } catch {
    // ignore — may throw "No entities to delete"
  }

  // Wait 10 seconds for async cleanup to propagate
  console.log("[integration] Waiting 10s for cleanup to propagate...");
  await new Promise((r) => setTimeout(r, 10_000));
  console.log("[integration] Pre-test cleanup done.");
}
