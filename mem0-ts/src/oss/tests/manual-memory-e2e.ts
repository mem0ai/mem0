/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * Manual integration test #2: End-to-end through memory/index.ts
 * 
 * This test pre-inserts data into Valkey via ValkeyDB directly, then
 * uses Memory.search() and Memory.getAll() to verify the final MemoryItem
 * output shape is correct (entity IDs in snake_case, timestamps in camelCase,
 * no metadata leakage).
 * 
 * Requires: Valkey 8.x at 127.0.0.2:6379 with search module.
 * 
 * Run from mem0-ts/:
 *   npx ts-node --transpile-only --compiler-options '{"module":"commonjs","moduleResolution":"node"}' \
 *     src/oss/tests/manual-memory-e2e.ts
 */

// Disable telemetry BEFORE importing Memory — prevents network calls that hang
process.env.MEM0_TELEMETRY = "false";

const { ValkeyDB } = require("../src/vector_stores/valkey") as { ValkeyDB: any };

// Monkey-patch factories BEFORE importing Memory
const factory = require("../src/utils/factory");
const FIXED_VEC = [0.25, 0.5, 0.75, 1.0];

factory.EmbedderFactory.create = () => ({
  embed: async () => FIXED_VEC,
  embedBatch: async (texts: string[]) => texts.map(() => FIXED_VEC),
});

factory.LLMFactory.create = () => ({
  generateResponse: async () => "[]",
});

// Stub getOrCreateMem0UserId to prevent network call
try {
  const clientConfig = require("../../../client/config");
  if (clientConfig.getOrCreateMem0UserId) {
    clientConfig.getOrCreateMem0UserId = async () => "test-user-id";
  }
} catch { /* ignore if module not found */ }

// Stub captureClientEvent to prevent network telemetry
try {
  const telemetry = require("../src/utils/telemetry");
  if (telemetry.captureClientEvent) {
    telemetry.captureClientEvent = async () => {};
  }
} catch { /* ignore */ }

const { Memory } = require("../src/memory/index") as { Memory: any };

const VALKEY_URL = "valkey://127.0.0.2:6379";
const COLLECTION = `e2e_test_${Date.now()}`;
const DIMS = 4;

function assert(condition: boolean, msg: string) {
  if (!condition) throw new Error(`ASSERTION FAILED: ${msg}`);
}

async function main() {
  console.log("=== Integration Test #2: End-to-end through memory/index.ts ===\n");

  // --- Pre-insert data via ValkeyDB directly ---
  const store = new ValkeyDB({
    collectionName: COLLECTION,
    embeddingModelDims: DIMS,
    valkeyUrl: VALKEY_URL,
  });
  await store.initialize();

  await store.insert(
    [FIXED_VEC, FIXED_VEC],
    ["mem-e2e-1", "mem-e2e-2"],
    [
      {
        data: "Alice likes cats",
        hash: "h1",
        created_at: "2024-06-01T12:00:00.000Z",
        user_id: "alice",
        agent_id: "bot1",
        run_id: "run1",
      },
      {
        data: "Bob likes dogs",
        hash: "h2",
        created_at: "2024-06-02T12:00:00.000Z",
        user_id: "bob",
      },
    ],
  );
  console.log("✓ Pre-inserted 2 memories into Valkey\n");

  // --- Create Memory instance with explicit dimension to skip probe ---
  const memory = new Memory({
    embedder: { provider: "openai", config: {} },
    llm: { provider: "openai", config: {} },
    vectorStore: {
      provider: "valkey",
      config: {
        collectionName: COLLECTION,
        embeddingModelDims: DIMS,
        dimension: DIMS,  // explicit — skips dimension probe
        valkeyUrl: VALKEY_URL,
      },
    },
  });

  // Wait for async init to complete
  await new Promise((r) => setTimeout(r, 1000));
  console.log("✓ Memory instance created\n");

  // --- Test search() ---
  console.log("--- memory.search() ---");
  const searchResult = await memory.search("cats", {
    filters: { user_id: "alice" },
  });
  console.log("Search results:", JSON.stringify(searchResult, null, 2));

  assert(searchResult.results.length > 0, "search should return results");
  const sr = searchResult.results[0];
  assert(sr.user_id === "alice", `search result user_id should be 'alice', got '${sr.user_id}'`);
  assert(sr.agent_id === "bot1", `search result agent_id should be 'bot1', got '${sr.agent_id}'`);
  assert(sr.run_id === "run1", `search result run_id should be 'run1', got '${sr.run_id}'`);
  assert(sr.createdAt !== undefined, "search result createdAt should exist");
  assert(sr.memory === "Alice likes cats", `memory text should match, got '${sr.memory}'`);
  // Verify NO leakage into metadata
  assert(sr.metadata?.userId === undefined, "userId should NOT be in metadata");
  assert(sr.metadata?.agentId === undefined, "agentId should NOT be in metadata");
  assert(sr.metadata?.runId === undefined, "runId should NOT be in metadata");
  assert(sr.metadata?.user_id === undefined, "user_id should NOT be in metadata (it's top-level)");
  console.log("✓ SEARCH assertions passed\n");

  // --- Test getAll() ---
  console.log("--- memory.getAll() ---");
  const allResult = await memory.getAll({
    filters: { user_id: "alice" },
  });
  console.log("GetAll results:", JSON.stringify(allResult, null, 2));

  assert(allResult.results.length > 0, "getAll should return results");
  const ar = allResult.results[0];
  assert(ar.user_id === "alice", `getAll result user_id should be 'alice', got '${ar.user_id}'`);
  assert(ar.createdAt !== undefined, "getAll result createdAt should exist");
  assert(ar.metadata?.userId === undefined, "userId should NOT be in metadata (getAll)");
  console.log("✓ GETALL assertions passed\n");

  // --- Cleanup ---
  await store.deleteCol();
  await store.close();

  console.log("=== ALL E2E ASSERTIONS PASSED ===");
  process.exit(0);
}

main().catch((err) => {
  console.error("FAILED:", err);
  process.exit(1);
});
