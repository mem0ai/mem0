import { describe, expect, it } from "vitest";
import { formatRecallMessages, recallMemories } from "../src/recall.js";
import { createFakeStore } from "./helpers.js";

describe("formatRecallMessages", () => {
  it("drops empty memories and empty ids", () => {
    expect(
      formatRecallMessages([
        { id: "1", memory: " likes tea " },
        { id: "2", memory: "   " },
        { id: "  ", memory: "kept text" },
      ]),
    ).toEqual([{ id: "1", content: "likes tea" }]);
  });
});

describe("recallMemories", () => {
  it("searches inside the locked scope and returns keyed messages", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const result = await recallMemories({
      store,
      scopeKey: "scope_abc",
      query: "What does the user drink?",
      topK: 3,
      threshold: 0.5,
      rerank: true,
    });

    expect(store.searched).toEqual([
      {
        query: "What does the user drink?",
        userId: "scope_abc",
        topK: 3,
        threshold: 0.5,
        rerank: true,
      },
    ]);
    expect(result).toEqual({
      messages: [{ id: "mem_1", content: "User likes tea" }],
    });
  });

  it("returns null for an empty query", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "x" }]);
    await expect(
      recallMemories({
        store,
        scopeKey: "scope_abc",
        query: "   ",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      }),
    ).resolves.toBeNull();
    expect(store.searched).toEqual([]);
  });

  it("returns null when search has no usable hits", async () => {
    const store = createFakeStore([{ id: "  ", memory: "   " }]);
    await expect(
      recallMemories({
        store,
        scopeKey: "scope_abc",
        query: "tea",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      }),
    ).resolves.toBeNull();
  });
});
