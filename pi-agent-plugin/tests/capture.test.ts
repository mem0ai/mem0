import { describe, it, expect } from "vitest";
import { extractConversation } from "../src/capture/index.ts";

describe("extractConversation", () => {
  it("extracts only user messages, skips assistant", () => {
    const messages = [
      { role: "user", content: "Hello" },
      { role: "assistant", content: "Hi there!" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ role: "user", content: "Hello" });
  });

  it("filters out tool and assistant messages", () => {
    const messages = [
      { role: "user", content: "Search" },
      { role: "assistant", content: [{ type: "tool_use", id: "x", name: "mem0" }] },
      { role: "tool", content: "results" },
      { role: "assistant", content: "Here are results" },
    ];
    const result = extractConversation(messages);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ role: "user", content: "Search" });
  });

  it("extracts text from user content arrays", () => {
    const messages = [
      { role: "user", content: [{ type: "text", text: "Hello world" }] },
    ];
    const result = extractConversation(messages);
    expect(result[0].content).toBe("Hello world");
  });

  it("returns empty array for empty input", () => {
    expect(extractConversation([])).toEqual([]);
  });
});
