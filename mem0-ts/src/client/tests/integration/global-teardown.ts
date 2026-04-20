/**
 * Jest global teardown for integration tests.
 *
 * Runs a full project cleanup after all integration tests complete
 * so no test data is left behind.
 */

export default async function globalTeardown() {
  const pkg = require("../../../../package.json");
  (globalThis as any).__MEM0_SDK_VERSION__ = pkg.version;

  const apiKey = process.env.MEM0_API_KEY;
  if (!apiKey) return;

  const { MemoryClient } = await import("../../mem0");
  const client = new MemoryClient({ apiKey });
  await client.ping();

  console.log("[integration] Running post-test cleanup...");

  try {
    await client.deleteAll({
      userId: "*",
      agentId: "*",
      appId: "*",
      runId: "*",
    });
  } catch {
    // ignore
  }

  try {
    await client.deleteUsers();
  } catch {
    // ignore
  }

  console.log("[integration] Post-test cleanup done.");
}
