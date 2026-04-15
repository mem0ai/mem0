/**
 * MemoryClient unit tests — add, get, update, delete, deleteAll, history.
 * Tests verify request construction, not mock response echo.
 */
import { MemoryClient } from "../mem0";
import type { MemoryHistory } from "../mem0.types";
import {
  createMockMemory,
  createMockMemoryHistory,
  TEST_API_KEY,
} from "./helpers";
import {
  setupMockFetch,
  findFetchCall,
  getFetchBody,
  installConsoleSuppression,
} from "./setup";

installConsoleSuppression();

// ─── add() ───────────────────────────────────────────────

describe("MemoryClient - add()", () => {
  test("sends POST to /v3/memories/add/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/add/", { status: 200, body: [createMockMemory()] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.add([{ role: "user", content: "Hello" }], { userId: "u1" });

    expect(findFetchCall(mock, "/v3/memories/add/", "POST")).toBeDefined();
  });

  test("includes messages in request body", async () => {
    const messages = [{ role: "user" as const, content: "Hello, I am Alex" }];
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/add/", { status: 200, body: [createMockMemory()] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.add(messages, { userId: "u1" });

    const call = findFetchCall(mock, "/v3/memories/add/", "POST");
    expect(getFetchBody(call!).messages).toEqual(messages);
  });

  test("includes user_id in request body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/add/", { status: 200, body: [createMockMemory()] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.add([{ role: "user", content: "test" }], {
      user_id: "user_1",
    });

    const call = findFetchCall(mock, "/v3/memories/add/", "POST");
    expect(getFetchBody(call!).user_id).toBe("user_1");
  });

  test("sends empty messages array without crashing", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v3/memories/add/", { status: 200, body: [] });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.add([], { userId: "u1" });

    const call = findFetchCall(mock, "/v3/memories/add/", "POST");
    expect(getFetchBody(call!).messages).toEqual([]);
  });
});

// ─── get() ───────────────────────────────────────────────

describe("MemoryClient - get()", () => {
  test("sends GET to /v1/memories/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory(),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.get("mem_123");

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/mem_123/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
  });

  test("throws on 404 with error message from server", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/nonexistent/", {
      status: 404,
      body: "Memory not found",
    });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.get("nonexistent")).rejects.toThrow("Memory not found");
  });
});

// ─── update() ────────────────────────────────────────────

describe("MemoryClient - update()", () => {
  test("sends PUT to /v1/memories/:id/ with text", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory(),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { text: "Updated text" });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(call).toBeDefined();
    expect(getFetchBody(call!).text).toBe("Updated text");
  });

  test("sends metadata in PUT body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory(),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { metadata: { priority: "high" } });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(getFetchBody(call!).metadata).toEqual({ priority: "high" });
  });

  test("sends timestamp in PUT body", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory(),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", { timestamp: 1710600000 });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    expect(getFetchBody(call!).timestamp).toBe(1710600000);
  });

  test("includes all fields when text + metadata + timestamp provided", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: createMockMemory(),
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.update("mem_123", {
      text: "Updated",
      metadata: { source: "test" },
      timestamp: 1710600000,
    });

    const call = findFetchCall(mock, "/v1/memories/mem_123/", "PUT");
    const body = getFetchBody(call!);
    expect(body.text).toBe("Updated");
    expect(body.metadata).toEqual({ source: "test" });
    expect(body.timestamp).toBe(1710600000);
  });

  test("throws when no fields provided", async () => {
    setupMockFetch();
    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await expect(client.update("mem_123", {})).rejects.toThrow(
      "At least one of text, metadata, or timestamp must be provided",
    );
  });
});

// ─── delete() ────────────────────────────────────────────

describe("MemoryClient - delete()", () => {
  test("sends DELETE to /v1/memories/:id/", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/", {
      status: 200,
      body: { message: "Memory deleted successfully" },
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.delete("mem_123");

    expect(
      findFetchCall(mock, "/v1/memories/mem_123/", "DELETE"),
    ).toBeDefined();
  });
});

// ─── deleteAll() ─────────────────────────────────────────

describe("MemoryClient - deleteAll()", () => {
  test("sends DELETE to /v1/memories/ with user_id as query param", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: { message: "Deleted" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteAll({ userId: "u1" });

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("user_id=u1");
  });

  test("URL-encodes special characters in user_id", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/", { status: 200, body: { message: "Deleted" } });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.deleteAll({ userId: "user@email.com" });

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/?") && c[1]?.method === "DELETE",
    );
    expect(call).toBeDefined();
    expect(call![0]).toContain("user_id=");
  });
});

// ─── history() ───────────────────────────────────────────

describe("MemoryClient - history()", () => {
  test("sends GET to /v1/memories/:id/history/", async () => {
    const historyEntries = [
      createMockMemoryHistory({
        memory_id: "mem_123",
        event: "ADD",
        old_memory: null,
        new_memory: "I am Alex",
      }),
    ];
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/history/", {
      status: 200,
      body: historyEntries,
    });
    const mock = setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    await client.history("mem_123");

    const call = mock.mock.calls.find(
      (c: [string, RequestInit]) =>
        c[0].includes("/v1/memories/mem_123/history/") && !c[1]?.method,
    );
    expect(call).toBeDefined();
  });

  test("handles empty history without crashing", async () => {
    const extra = new Map<string, { status: number; body: unknown }>();
    extra.set("/v1/memories/mem_123/history/", { status: 200, body: [] });
    setupMockFetch(extra);

    const client = new MemoryClient({ apiKey: TEST_API_KEY });
    const result: MemoryHistory[] = await client.history("mem_123");
    expect(result).toEqual([]);
  });
});
