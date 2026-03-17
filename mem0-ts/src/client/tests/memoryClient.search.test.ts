/**
 * MemoryClient unit tests — search (v1/v2 routing, filters).
 * Tests verify request construction, not mock response echo.
 */
import { MemoryClient } from "../mem0";
import type { Memory } from "../mem0.types";
import { createMockMemory, TEST_API_KEY } from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

describe("MemoryClient - search()", () => {
  test("sends POST to /v1/memories/search/ by default", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("What is my name?", { user_id: "u1" });

    expect(findFetchCall(mock, "/v1/memories/search/", "POST")).toBeDefined();
  });

  test("includes query in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("What is my name?", { user_id: "u1" });

    const call = findFetchCall(mock, "/v1/memories/search/", "POST");
    expect(getFetchBody(call!).query).toBe("What is my name?");
  });

  test("includes user_id in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("test", { user_id: "u1" });

    const call = findFetchCall(mock, "/v1/memories/search/", "POST");
    expect(getFetchBody(call!).user_id).toBe("u1");
  });

  test("uses /v2/memories/search/ when api_version=v2", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/search/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("test", { user_id: "u1", api_version: "v2" });

    expect(findFetchCall(mock, "/v2/memories/search/", "POST")).toBeDefined();
  });

  test("passes filters through to the v2 API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v2/memories/search/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("query", {
      api_version: "v2",
      filters: { OR: [{ user_id: "u1" }, { agent_id: "a1" }] },
    });

    const call = findFetchCall(mock, "/v2/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual({
      OR: [{ user_id: "u1" }, { agent_id: "a1" }],
    });
  });

  test("does not crash when called without options", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result: Memory[] = await client.search("query");
    expect(Array.isArray(result)).toBe(true);
  });

  test("handles empty results array", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/search/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result: Memory[] = await client.search("nonexistent query", {
      user_id: "u1",
    });
    expect(result).toHaveLength(0);
  });
});
