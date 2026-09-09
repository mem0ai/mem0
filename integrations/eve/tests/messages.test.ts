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
});
