import { beforeEach, describe, expect, it, vi } from "vitest";

const { MemoryClient, add, search, get, getAll, del } = vi.hoisted(() => {
  const add = vi.fn();
  const search = vi.fn();
  const get = vi.fn();
  const getAll = vi.fn();
  const del = vi.fn();
  const MemoryClient = vi.fn(
    class {
      add = add;
      search = search;
      get = get;
      getAll = getAll;
      delete = del;
    },
  );
  return { MemoryClient, add, search, get, getAll, del };
});

vi.mock("mem0ai", () => ({
  default: MemoryClient,
}));

import {
  createLazyStore,
  createMem0Store,
  parseAddResult,
  parseMemoryRecord,
  parseSearchHit,
  resolveApiKey,
} from "../src/store.js";

describe("parseAddResult", () => {
  it("reports a pending event as queued", () => {
    expect(parseAddResult({ event_id: "evt_1", status: "PENDING" })).toEqual({
      status: "queued",
      eventId: "evt_1",
    });
  });

  it("reports a succeeded event as completed", () => {
    expect(parseAddResult({ event_id: "evt_1", status: "SUCCEEDED" })).toEqual({
      status: "completed",
      eventId: "evt_1",
    });
  });

  it("treats a memory-results array as completed", () => {
    expect(parseAddResult([{ id: "m1", memory: "tea" }])).toEqual({
      status: "completed",
    });
  });

  it("does not report a failed event as queued", () => {
    expect(parseAddResult({ event_id: "evt_1", status: "FAILED" })).toEqual({
      status: "completed",
      eventId: "evt_1",
    });
  });

  it("does not report an event with no status as queued", () => {
    expect(parseAddResult({ event_id: "evt_1" })).toEqual({
      status: "completed",
      eventId: "evt_1",
    });
  });
});

describe("parseSearchHit", () => {
  it("accepts id, memory_id, nested text, and numeric ids", () => {
    expect(parseSearchHit({ id: 12, memory: "tea" })).toEqual({
      id: "12",
      memory: "tea",
    });
    expect(
      parseSearchHit({ memory_id: "m1", data: { memory: "nested" } }),
    ).toEqual({ id: "m1", memory: "nested" });
    expect(parseSearchHit({ id: "m2", text: "plain" })).toEqual({
      id: "m2",
      memory: "plain",
    });
    expect(parseSearchHit({ id: "", memory: "x" })).toBeNull();
  });
});

describe("parseMemoryRecord", () => {
  it("requires id and userId", () => {
    expect(
      parseMemoryRecord({
        id: "m1",
        user_id: "scope_abc",
        metadata: { source: "eve" },
      }),
    ).toEqual({
      id: "m1",
      userId: "scope_abc",
      metadata: { source: "eve" },
    });
    expect(parseMemoryRecord({ id: "m1" })).toBeNull();
  });
});

describe("resolveApiKey", () => {
  it("trims string keys and rejects empty values", async () => {
    await expect(resolveApiKey("  token  ")).resolves.toBe("token");
    await expect(resolveApiKey("   ")).rejects.toThrow(/empty/);
  });

  it("resolves async getters", async () => {
    await expect(resolveApiKey(async () => "  secret  ")).resolves.toBe("secret");
    await expect(resolveApiKey(async () => "")).rejects.toThrow(/empty/);
  });
});

describe("createLazyStore", () => {
  it("retries after a failed factory call", async () => {
    let calls = 0;
    const load = createLazyStore(async () => {
      calls += 1;
      if (calls === 1) {
        throw new Error("unavailable");
      }
      return { name: "store" } as never;
    });

    await expect(load()).rejects.toThrow("unavailable");
    await expect(load()).resolves.toEqual({ name: "store" });
    expect(calls).toBe(2);
  });
});

describe("createMem0Store", () => {
  beforeEach(() => {
    add.mockReset();
    search.mockReset();
    get.mockReset();
    getAll.mockReset();
    del.mockReset();
    MemoryClient.mockClear();
  });

  it("constructs the client with a resolved key and host", async () => {
    const store = await createMem0Store({
      apiKey: async () => "  m0-live  ",
      host: "https://api.mem0.ai",
    });
    expect(store).toBeTruthy();
    expect(MemoryClient).toHaveBeenCalledWith({
      apiKey: "m0-live",
      host: "https://api.mem0.ai",
    });
  });

  it("forwards add, search, and metadata filters", async () => {
    search.mockResolvedValue({
      results: [{ id: "m1", memory: "likes tea" }, { id: 2, memory: "" }],
    });
    getAll.mockResolvedValue({
      results: [{ id: "m9", userId: "scope_abc", metadata: { operation_id: "op_1" } }],
    });
    add.mockResolvedValue({ event_id: "evt_1", status: "SUCCEEDED" });

    const store = await createMem0Store({
      apiKey: "m0-test",
      host: "https://api.mem0.ai",
    });

    const addResult = await store.add([{ role: "user", content: "I like tea" }], {
      userId: "scope_abc",
      infer: false,
      metadata: { source: "eve", operation_id: "op_1" },
    });
    expect(addResult).toEqual({ status: "completed", eventId: "evt_1" });
    const found = await store.search("tea", {
      userId: "scope_abc",
      topK: 3,
      threshold: 0.5,
      rerank: true,
    });
    const existing = await store.listByMetadata({
      userId: "scope_abc",
      metadata: { operation_id: "op_1" },
    });

    expect(add).toHaveBeenCalledWith(
      [{ role: "user", content: "I like tea" }],
      {
        userId: "scope_abc",
        infer: false,
        metadata: { source: "eve", operation_id: "op_1" },
      },
    );
    expect(search).toHaveBeenCalledWith("tea", {
      filters: { user_id: "scope_abc" },
      topK: 3,
      threshold: 0.5,
      rerank: true,
    });
    expect(found.results).toEqual([{ id: "m1", memory: "likes tea" }]);
    expect(existing).toEqual([
      {
        id: "m9",
        userId: "scope_abc",
        metadata: { operation_id: "op_1" },
      },
    ]);
  });

  it("surfaces a pending platform write as queued", async () => {
    const store = await createMem0Store({
      apiKey: "m0-test",
      host: "https://api.mem0.ai",
    });
    add.mockResolvedValueOnce({ event_id: "evt_9", status: "PENDING" });
    await expect(
      store.add([{ role: "user", content: "I like tea" }], {
        userId: "scope_abc",
        infer: true,
        metadata: { source: "eve" },
      }),
    ).resolves.toEqual({ status: "queued", eventId: "evt_9" });
  });

  it("accepts a bare search array and rejects unknown envelopes", async () => {
    const store = await createMem0Store({
      apiKey: "m0-test",
      host: "https://api.mem0.ai",
    });
    search.mockResolvedValueOnce([{ id: "m1", memory: "tea" }]);
    await expect(
      store.search("tea", {
        userId: "scope_abc",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      }),
    ).resolves.toEqual({ results: [{ id: "m1", memory: "tea" }] });

    search.mockResolvedValueOnce({ memories: "nope" });
    await expect(
      store.search("tea", {
        userId: "scope_abc",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      }),
    ).rejects.toThrow(/unexpected response shape/);
  });

  it("deletes only when the memory belongs to the scope", async () => {
    const store = await createMem0Store({
      apiKey: "m0-test",
      host: "https://api.mem0.ai",
    });

    get.mockResolvedValueOnce({ id: "m1", userId: "scope_abc" });
    await store.delete("m1", "scope_abc");
    expect(del).toHaveBeenCalledWith("m1");

    get.mockResolvedValueOnce({ id: "m2", user_id: "other" });
    await expect(store.delete("m2", "scope_abc")).rejects.toThrow(/Memory not found/);
    expect(del).toHaveBeenCalledTimes(1);

    get.mockRejectedValueOnce(new Error("Memory not found"));
    await expect(store.delete("missing", "scope_abc")).rejects.toThrow(
      /Memory not found/,
    );
  });
});
