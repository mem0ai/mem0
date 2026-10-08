import { describe, expect, it } from "vitest";
import {
  completedTurnMessages,
  conversationMessages,
  extractText,
  lastUserText,
} from "../src/messages.js";

describe("extractText", () => {
  it("reads a string", () => {
    expect(extractText("  hello  ")).toBe("hello");
  });

  it("joins text parts", () => {
    expect(
      extractText([
        { type: "text", text: "I like" },
        { type: "text", text: "tea" },
      ]),
    ).toBe("I like\ntea");
  });

  it("reads a single text object", () => {
    expect(extractText({ type: "text", text: "  solo  " })).toBe("solo");
  });

  it("ignores non-text parts", () => {
    expect(extractText([{ type: "image", url: "x" }])).toBe("");
  });

  it("ignores reasoning parts and keeps only the final text", () => {
    expect(
      extractText([
        { type: "reasoning", text: "speculation" },
        { type: "text", text: "Noted." },
      ]),
    ).toBe("Noted.");
  });

  it("still reads an untyped text object", () => {
    expect(extractText({ text: "  bare  " })).toBe("bare");
  });
});

describe("lastUserText", () => {
  it("returns the last user message", () => {
    expect(
      lastUserText([
        { role: "user", content: "first" },
        { role: "assistant", content: "ok" },
        { role: "user", content: "second" },
      ]),
    ).toBe("second");
  });

  it("returns empty when there is no user text", () => {
    expect(lastUserText([{ role: "assistant", content: "hi" }])).toBe("");
  });
});

describe("conversationMessages", () => {
  it("keeps user and assistant text only", () => {
    expect(
      conversationMessages([
        { role: "system", content: "ignore" },
        { role: "user", content: "hello" },
        { role: "assistant", content: "hi" },
        { role: "user", content: "" },
      ]),
    ).toEqual([
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi" },
    ]);
  });
});

describe("completedTurnMessages", () => {
  it("pairs the current user turn with the latest assistant reply", () => {
    expect(
      completedTurnMessages({
        turnInput: [{ role: "user", content: "I like tea" }],
        messages: [
          { role: "user", content: "older" },
          { role: "assistant", content: "older reply" },
          { role: "user", content: "I like tea" },
          { role: "assistant", content: "Noted." },
        ],
      }),
    ).toEqual([
      { role: "user", content: "I like tea" },
      { role: "assistant", content: "Noted." },
    ]);
  });

  it("skips capture when the turn has no user text", () => {
    expect(
      completedTurnMessages({
        turnInput: [{ role: "assistant", content: "hello" }],
        messages: [{ role: "assistant", content: "hello" }],
      }),
    ).toEqual([]);
  });

  it("does not attach a previous turn's answer to a tool-only turn", () => {
    // Older Q&A, then a new user message whose only assistant output is a
    // tool call (no text). The stale "older reply" must not be captured.
    expect(
      completedTurnMessages({
        turnInput: [{ role: "user", content: "new question" }],
        messages: [
          { role: "user", content: "older question" },
          { role: "assistant", content: "older reply" },
          { role: "user", content: "new question" },
          { role: "assistant", content: [{ type: "tool-call", id: "t1" }] },
        ],
      }),
    ).toEqual([{ role: "user", content: "new question" }]);
  });

  it("captures all assistant text in a text/tool-call/text turn", () => {
    expect(
      completedTurnMessages({
        turnInput: [{ role: "user", content: "Q" }],
        messages: [
          { role: "user", content: "Q" },
          { role: "assistant", content: "part A" },
          { role: "assistant", content: [{ type: "tool-call", id: "t1" }] },
          { role: "assistant", content: "part B" },
        ],
      }),
    ).toEqual([
      { role: "user", content: "Q" },
      { role: "assistant", content: "part A\npart B" },
    ]);
  });

  it("captures this turn's assistant reply, not an earlier one", () => {
    expect(
      completedTurnMessages({
        turnInput: [{ role: "user", content: "new question" }],
        messages: [
          { role: "user", content: "older question" },
          { role: "assistant", content: "older reply" },
          { role: "user", content: "new question" },
          { role: "assistant", content: "new reply" },
        ],
      }),
    ).toEqual([
      { role: "user", content: "new question" },
      { role: "assistant", content: "new reply" },
    ]);
  });
});
