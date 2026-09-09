import { describe, expect, it } from "vitest";
import { captureCompletedTurn } from "../src/capture.js";
import { createFakeStore } from "./helpers.js";

describe("captureCompletedTurn", () => {
  it("adds the current turn under the locked scope", async () => {
    const store = createFakeStore();
    const captured = await captureCompletedTurn({
      store,
      scopeKey: "scope_abc",
      infer: true,
      metadata: { source: "eve" },
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
      infer: true,
      metadata: {},
      turnInput: [],
      messages: [],
    });
    expect(captured).toBe(false);
    expect(store.added).toEqual([]);
  });
});
