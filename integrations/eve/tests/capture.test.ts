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

  it("dedupes a replay once the prior write is visible", async () => {
    const store = createFakeStore();
    const args = {
      store,
      scopeKey: "scope_abc",
      operationId: "op_dedup",
      infer: true,
      metadata: { source: "eve", operation_id: "op_dedup" },
      turnInput: [{ role: "user", content: "I am vegetarian" }],
      messages: [
        { role: "user", content: "I am vegetarian" },
        { role: "assistant", content: "Got it." },
      ],
    };
    // First write is immediately visible (completed), so the replay is deduped.
    expect(await captureCompletedTurn(args)).toBe(true);
    expect(await captureCompletedTurn(args)).toBe(false);
    expect(store.added).toHaveLength(1);
  });

  it("cannot dedupe while the prior write is still pending (best-effort)", async () => {
    // Documents the known limitation: with infer:true the first write is a
    // PENDING event whose memory is not yet visible, so the metadata lookup
    // finds nothing and a restart replay writes the same operation again.
    const store = createFakeStore([], { pendingWrites: true });
    const args = {
      store,
      scopeKey: "scope_abc",
      operationId: "op_pending",
      infer: true,
      metadata: { source: "eve", operation_id: "op_pending" },
      turnInput: [{ role: "user", content: "I am vegetarian" }],
      messages: [
        { role: "user", content: "I am vegetarian" },
        { role: "assistant", content: "Got it." },
      ],
    };
    expect(await captureCompletedTurn(args)).toBe(true);
    expect(await captureCompletedTurn(args)).toBe(true);
    expect(store.added).toHaveLength(2);
  });

  it("does not dedupe concurrent replays that both pass the lookup (best-effort)", async () => {
    // Two workers on separate provider instances both clear the metadata check
    // before either write lands, so both capture the same operation.
    const store = createFakeStore([], { pendingWrites: true });
    const args = {
      store,
      scopeKey: "scope_abc",
      operationId: "op_concurrent",
      infer: true,
      metadata: { source: "eve", operation_id: "op_concurrent" },
      turnInput: [{ role: "user", content: "I am vegetarian" }],
      messages: [
        { role: "user", content: "I am vegetarian" },
        { role: "assistant", content: "Got it." },
      ],
    };
    const [first, second] = await Promise.all([
      captureCompletedTurn(args),
      captureCompletedTurn(args),
    ]);
    expect(first).toBe(true);
    expect(second).toBe(true);
    expect(store.added).toHaveLength(2);
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
