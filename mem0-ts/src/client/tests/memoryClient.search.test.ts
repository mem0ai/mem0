/**
 * MemoryClient unit tests — search (v3 endpoint, filters).
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
  test("sends POST to /v3/memories/search/ by default", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("What is my name?", {
      filters: { userId: "u1" },
    });

    expect(findFetchCall(mock, "/v3/memories/search/", "POST")).toBeDefined();
  });

  test("includes query in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("What is my name?", {
      filters: { userId: "u1" },
    });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    expect(getFetchBody(call!).query).toBe("What is my name?");
  });

  test("passes filters through to the API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("test", { filters: { userId: "u1" } });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    expect(getFetchBody(call!).filters).toEqual({ user_id: "u1" });
  });

  test("passes complex OR filters through to the API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("query", {
      filters: { OR: [{ user_id: "u1" }, { agent_id: "a1" }] },
    });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual({
      OR: [{ user_id: "u1" }, { agent_id: "a1" }],
    });
  });

  test("does not crash when called without options", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.search("query");
    expect(result).toHaveProperty("results");
  });

  test("handles empty results array", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result = await client.search("nonexistent query", {
      filters: { userId: "u1" },
    });
    expect(result.results).toHaveLength(0);
  });
});
