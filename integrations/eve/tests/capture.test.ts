import { describe, expect, it } from "vitest";
import { captureCompletedTurn } from "../src/capture.js";
import { createFakeStore } from "./helpers.js";

describe("captureCompletedTurn", () => {
  it("adds the current turn under the locked scope", async () => {
    const store = createFakeStore();
    const captured = await captureCompletedTurn({
      store,
      scopeKey: "scope_abc",
      operationId: "op_1",
      infer: false,
      metadata: { source: "eve", operation_id: "op_1" },
      turnInput: [{ role: "user", content: "I am vegetarian" }],
      messages: [
        { role: "user", content: "I am vegetarian" },
        { role: "assistant", content: "Got it." },
      ],
    });

    expect(captured).toBe(true);
    expect(store.added).toEqual([
      {
        userId: "scope_abc",
        infer: false,
        metadata: { source: "eve", operation_id: "op_1" },
        messages: [
          { role: "user", content: "I am vegetarian" },
          { role: "assistant", content: "Got it." },
        ],
      },
    ]);
  });

  it("does not write when the turn has no user text", async () => {
    const store = createFakeStore();
    const captured = await captureCompletedTurn({
      store,
      scopeKey: "scope_abc",
      operationId: "op_1",
      infer: true,
      metadata: { operation_id: "op_1" },
      turnInput: [],
      messages: [],
    });
    expect(captured).toBe(false);
    expect(store.added).toEqual([]);
  });

  it("skips add when the operation id was already captured", async () => {
    const store = createFakeStore([
      {
        id: "mem_existing",
        memory: "already stored",
        metadata: { operation_id: "op_replay" },
      },
    ]);
    const captured = await captureCompletedTurn({
      store,
      scopeKey: "scope_abc",
      operationId: "op_replay",
      infer: true,
      metadata: { operation_id: "op_replay" },
      turnInput: [{ role: "user", content: "I am vegetarian" }],
      messages: [
        { role: "user", content: "I am vegetarian" },
        { role: "assistant", content: "Got it." },
      ],
    });

    expect(captured).toBe(false);
    expect(store.added).toEqual([]);
  });
});
