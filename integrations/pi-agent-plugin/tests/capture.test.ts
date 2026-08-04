import { describe, it, expect } from "vitest";
import { extractConversation } from "../src/capture/index.ts";

describe("extractConversation", () => {
  it("extracts user and assistant text messages", () => {
    const messages = [
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Hi there!" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ role: "user", content: "Hello" });
    expect(result[1]).toEqual({ role: "assistant", content: "Hi there!" });
  });

  it("skips assistant tool_use blocks, keeps text blocks", () => {
    const messages = [
      { role: "user", content: "Search" },
      { role: "assistant", content: [{ type: "tool_use", id: "x", name: "mem0" }] },
      { role: "tool", content: "results" },
      { role: "assistant", content: "Here are the results" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ role: "user", content: "Search" });
    expect(result[1]).toEqual({ role: "assistant", content: "Here are the results" });
  });

  it("extracts text from content arrays for both roles", () => {
    const messages = [
      { role: "user", content: [{ type: "text", text: "Hello world" }] },
      { role: "assistant", content: [{ type: "text", text: "Response" }, { type: "tool_use", id: "x" }] },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(2);
    expect(result[0].content).toBe("Hello world");
    expect(result[1].content).toBe("Response");
  });

  it("skips tool and system messages", () => {
    const messages = [
      { role: "system", content: "You are helpful" },
      { role: "user", content: "Hi" },
      { role: "tool", content: "tool output" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ role: "user", content: "Hi" });
  });

  it("skips assistant messages with only tool_use (no text)", () => {
    const messages = [
      { role: "assistant", content: [{ type: "tool_use", id: "x", name: "bash" }] },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(0);
  });

  it("returns empty array for empty input", () => {
    expect(extractConversation([])).toEqual([]);
  });
});
