import type { VectorStoreResult } from "../../src/types";

export const canonicalResultId = "canonical-result";

// Mixed casing is canonical: mem0-ts/src/oss/src/memory/index.ts:991-992 writes createdAt/updatedAt, and :1266-1267 reads them back unchanged.
export const canonicalResultPayload = {
  data: "canonical memory",
  hash: "canonical-hash",
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-02T00:00:00.000Z",
  user_id: "user-1",
  agent_id: "agent-1",
  run_id: "run-1",
  source: "compat-test",
};

export function expectCanonicalResultPayload(
  expectedId: string,
  getResult: VectorStoreResult | null,
  listResults: VectorStoreResult[],
  searchResults: VectorStoreResult[],
) {
  expect(getResult).not.toBeNull();
  const listedResult = listResults.find((result) => result.id === expectedId);
  const searchedResult = searchResults.find(
    (result) => result.id === expectedId,
  );

  expect(getResult!.id).toBe(expectedId);
  expect(listedResult?.id).toBe(expectedId);
  expect(searchedResult?.id).toBe(expectedId);
  expect(getResult!.payload).toStrictEqual(canonicalResultPayload);
  expect(listedResult!.payload).toStrictEqual(canonicalResultPayload);
  expect(searchedResult!.payload).toStrictEqual(canonicalResultPayload);
}
