/**
 * Jest global teardown for integration tests.
 *
 * Runs a full project cleanup after all integration tests complete
 * so no test data is left behind.
 */
import { MemoryClient } from "../../mem0";

export default async function globalTeardown() {
  const apiKey = process.env.MEM0_API_KEY;
  if (!apiKey) return;

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
