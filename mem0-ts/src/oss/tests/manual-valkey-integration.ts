/* eslint-disable @typescript-eslint/no-var-requires */
/**
 * Manual integration test #1: ValkeyDB direct — insert/search/get/update/delete cycle.
 * Run from mem0-ts/: npx ts-node --project tsconfig.test.json src/oss/tests/manual-valkey-integration.ts
 */

const { ValkeyDB } = require("../src/vector_stores/valkey") as { ValkeyDB: any };

const VALKEY_URL = "valkey://127.0.0.2:6379";
const COLLECTION = `integ_test_${Date.now()}`;
const DIMS = 4;

function assert(condition: boolean, msg: string) {
  if (!condition) throw new Error(`ASSERTION FAILED: ${msg}`);
}

async function main() {
  console.log("=== Integration Test #1: ValkeyDB direct ===\n");

  const store = new ValkeyDB({
    collectionName: COLLECTION,
    embeddingModelDims: DIMS,
    valkeyUrl: VALKEY_URL,
  });
  await store.initialize();
  console.log("✓ Store initialized\n");

  // --- INSERT ---
  const vec = [0.1, 0.2, 0.3, 0.4];
  await store.insert(
    [vec],
    ["mem-integ-1"],
    [
      {
        data: "Alice likes cats",
        hash: "h1",
        created_at: "2024-06-01T12:00:00.000Z",
        user_id: "u1",
        agent_id: "a1",
        run_id: "r1",
      },
    ],
  );
  console.log("✓ Inserted mem-integ-1\n");

  // --- GET ---
  const getResult = await store.get("mem-integ-1");
  console.log("GET result payload:", JSON.stringify(getResult?.payload, null, 2));
  assert(getResult !== null, "get() returned null");
  assert(getResult!.payload.user_id === "u1", "user_id should be 'u1'");
  assert(getResult!.payload.agent_id === "a1", "agent_id should be 'a1'");
  assert(getResult!.payload.run_id === "r1", "run_id should be 'r1'");
  assert(getResult!.payload.userId === undefined, "userId should NOT exist");
  assert(getResult!.payload.agentId === undefined, "agentId should NOT exist");
  assert(getResult!.payload.runId === undefined, "runId should NOT exist");
  assert(getResult!.payload.createdAt !== undefined, "createdAt should exist");
  assert(getResult!.payload.created_at === undefined, "created_at should NOT exist");
  console.log("✓ GET assertions passed\n");

  // --- SEARCH ---
  const searchResults = await store.search(vec, 5, { user_id: "u1" });
  console.log("SEARCH results:", searchResults.length, "hits");
  console.log("SEARCH first payload:", JSON.stringify(searchResults[0]?.payload, null, 2));
  assert(searchResults.length > 0, "search should return at least 1 result");
  assert(searchResults[0].payload.user_id === "u1", "search result user_id should be 'u1'");
  assert(searchResults[0].payload.userId === undefined, "search result should NOT have userId");
  assert(searchResults[0].payload.createdAt !== undefined, "search result createdAt should exist");
  console.log("✓ SEARCH assertions passed\n");

  // --- SEARCH with non-matching filter ---
  const emptyResults = await store.search(vec, 5, { user_id: "nonexistent" });
  assert(emptyResults.length === 0, "search with non-matching filter should return empty");
  console.log("✓ SEARCH with non-matching filter returned empty\n");

  // --- UPDATE ---
  await store.update("mem-integ-1", vec, {
    data: "Alice likes cats and dogs",
    hash: "h1-updated",
    created_at: "2024-06-01T12:00:00.000Z",
    updated_at: "2024-06-02T14:00:00.000Z",
    user_id: "u1",
    agent_id: "a1",
    run_id: "r1",
  });
  console.log("✓ Updated mem-integ-1\n");

  const updatedResult = await store.get("mem-integ-1");
  console.log("GET after update payload:", JSON.stringify(updatedResult?.payload, null, 2));
  assert(updatedResult!.payload.user_id === "u1", "after update user_id should be 'u1'");
  assert(updatedResult!.payload.updatedAt !== undefined, "updatedAt should exist after update");
  assert(updatedResult!.payload.updated_at === undefined, "updated_at should NOT exist");
  assert(updatedResult!.payload.data === "Alice likes cats and dogs", "data should be updated");
  console.log("✓ UPDATE assertions passed\n");

  // --- DELETE ---
  await store.delete("mem-integ-1");
  const deletedResult = await store.get("mem-integ-1");
  assert(deletedResult === null, "get() after delete should return null");
  console.log("✓ DELETE assertions passed\n");

  // --- CLEANUP ---
  await store.deleteCol();
  await store.close();

  console.log("=== ALL ASSERTIONS PASSED ===");
}

main().catch((err) => {
  console.error("FAILED:", err);
  process.exit(1);
});
