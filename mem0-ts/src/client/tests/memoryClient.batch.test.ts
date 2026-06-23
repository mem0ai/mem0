/**
 * MemoryClient unit tests — batchUpdate, batchDelete.
 * Tests verify payload transformation (memoryId → memory_id, string → object).
 */
import { MemoryClient } from "../mem0";
import { TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

// ─── batchUpdate() ──────────────────────────────────────

describe("MemoryClient - batchUpdate()", () => {
  test("sends PUT to /v1/batch/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchUpdate([{ memoryId: "mem_1", text: "updated 1" }]);

    expect(findFetchCall(mock, "/v1/batch/", "PUT")).toBeDefined();
  });

  test("transforms memoryId to memory_id in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchUpdate([
      { memoryId: "mem_1", text: "updated 1" },
      { memoryId: "mem_2", text: "updated 2" },
    ]);

    const call = findFetchCall(mock, "/v1/batch/", "PUT");
    const body = getFetchBody(call!);
    expect(body.memories).toEqual([
      { memory_id: "mem_1", text: "updated 1" },
      { memory_id: "mem_2", text: "updated 2" },
    ]);
  });

  test("handles empty array without crashing", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchUpdate([]);

    const call = findFetchCall(mock, "/v1/batch/", "PUT");
    expect(getFetchBody(call!).memories).toEqual([]);
  });
});

// ─── batchDelete() ──────────────────────────────────────

describe("MemoryClient - batchDelete()", () => {
  test("sends DELETE to /v1/batch/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchDelete(["mem_1"]);

    expect(findFetchCall(mock, "/v1/batch/", "DELETE")).toBeDefined();
  });

  test("wraps string IDs into {memory_id} objects", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchDelete(["mem_1", "mem_2", "mem_3"]);

    const call = findFetchCall(mock, "/v1/batch/", "DELETE");
    expect(getFetchBody(call!).memories).toEqual([
      { memory_id: "mem_1" },
      { memory_id: "mem_2" },
      { memory_id: "mem_3" },
    ]);
  });

  test("handles empty array without crashing", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/batch/", { status: 200, body: { message: "OK" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.batchDelete([]);

    const call = findFetchCall(mock, "/v1/batch/", "DELETE");
    expect(getFetchBody(call!).memories).toEqual([]);
  });
});
