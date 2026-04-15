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
      filters: { user_id: "u1" },
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
      filters: { user_id: "u1" },
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
    await client.search("test", { filters: { user_id: "u1" } });

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

  test("passes complex AND filters through to the API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("query", {
      filters: {
        AND: [
          { user_id: "u1" },
          { created_at: { gte: "2024-01-01T00:00:00Z" } },
        ],
      },
    });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual({
      AND: [{ user_id: "u1" }, { created_at: { gte: "2024-01-01T00:00:00Z" } }],
    });
  });

  test("passes NOT filters through to the API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.search("query", {
      filters: {
        AND: [
          { user_id: "u1" },
          { NOT: { categories: { in: ["spam", "test"] } } },
        ],
      },
    });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual({
      AND: [
        { user_id: "u1" },
        { NOT: { categories: { in: ["spam", "test"] } } },
      ],
    });
  });

  test("passes complex nested AND/OR/NOT filters through to the API body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const complexFilter = {
      AND: [
        { user_id: "u1" },
        { created_at: { gte: "2024-01-01T00:00:00Z" } },
        {
          NOT: {
            OR: [
              { categories: { in: ["spam"] } },
              { categories: { in: ["test"] } },
            ],
          },
        },
      ],
    };
    await client.search("query", { filters: complexFilter });

    const call = findFetchCall(mock, "/v3/memories/search/", "POST");
    const body = getFetchBody(call!);
    expect(body.filters).toEqual(complexFilter);
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
      filters: { AND: [{ user_id: "u1" }] },
    });
    expect(result.results).toHaveLength(0);
  });
});

describe("MemoryClient - search() entity param rejection", () => {
  test("rejects user_id at top level", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(
      client.search("query", { user_id: "u1" } as any),
    ).rejects.toThrow(/filters/);
  });

  test("rejects agent_id at top level", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(
      client.search("query", { agent_id: "a1" } as any),
    ).rejects.toThrow(/filters/);
  });

  test("rejects app_id at top level", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(
      client.search("query", { app_id: "app1" } as any),
    ).rejects.toThrow(/filters/);
  });

  test("accepts filters with user_id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/search/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    // Should not throw
    await client.search("query", { filters: { AND: [{ user_id: "u1" }] } });
    expect(findFetchCall(mock, "/v3/memories/search/", "POST")).toBeDefined();
  });
});

describe("MemoryClient - getAll() entity param rejection", () => {
  test("rejects user_id at top level", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.getAll({ user_id: "u1" } as any)).rejects.toThrow(
      /filters/,
    );
  });

  test("rejects agent_id at top level", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.getAll({ agent_id: "a1" } as any)).rejects.toThrow(
      /filters/,
    );
  });

  test("accepts filters with user_id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/", {
      status: 200,
      body: { results: [] },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.getAll({ filters: { user_id: "u1" } });
    expect(findFetchCall(mock, "/v3/memories/", "POST")).toBeDefined();
  });
});
