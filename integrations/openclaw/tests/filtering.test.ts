import { describe, it, expect } from "vitest";
import {
  isNoiseMessage,
  isGenericAssistantMessage,
  isSessionSpecificContent,
  stripNoiseFromContent,
  filterMessagesForExtraction,
} from "../filtering.ts";

describe("isNoiseMessage", () => {
  it("returns true for heartbeat messages", () => {
    expect(isNoiseMessage("HEARTBEAT_OK")).toBe(true);
    expect(isNoiseMessage("NO_REPLY")).toBe(true);
  });

  it("returns true for single-word acknowledgments", () => {
    expect(isNoiseMessage("ok")).toBe(true);
    expect(isNoiseMessage("done")).toBe(true);
    expect(isNoiseMessage("thanks")).toBe(true);
  });

  it("returns false for substantive content", () => {
    expect(isNoiseMessage("My name is John and I live in Tokyo")).toBe(false);
  });
});

describe("isGenericAssistantMessage", () => {
  it("returns true for generic acknowledgments", () => {
    expect(isGenericAssistantMessage("I see you've shared this. How can I help?")).toBe(true);
    expect(isGenericAssistantMessage("Got it! How can I assist you?")).toBe(true);
  });

  it("returns false for substantive responses", () => {
    expect(isGenericAssistantMessage("Based on the code, the bug is in line 42 where the null check is missing.")).toBe(false);
  });
});

describe("isSessionSpecificContent", () => {
  it("returns true for tool availability discussions", () => {
    expect(isSessionSpecificContent(
      "I do not currently see Mem0 write/update/delete tools exposed in this session."
    )).toBe(true);
  });

  it("returns true for plugin capability statements", () => {
    expect(isSessionSpecificContent(
      "As of 2026-04-18, the openclaw-mem0 plugin does not expose a memory wiki capability."
    )).toBe(true);
  });

  it("returns true for session-specific tool lists", () => {
    expect(isSessionSpecificContent(
      "The tools I have access to in this session are memory_search and memory_get."
    )).toBe(true);
  });

  it("returns false for user preferences", () => {
    expect(isSessionSpecificContent(
      "My name is Kartik and I like to watch Pokemon."
    )).toBe(false);
  });

  it("returns false for technical facts that span sessions", () => {
    expect(isSessionSpecificContent(
      "The project uses TypeScript 5.0 and Node.js 20."
    )).toBe(false);
  });
});

describe("filterMessagesForExtraction", () => {
  it("filters out session-specific tool discussions", () => {
    const messages = [
      { role: "user", content: "What tools do you have access to?" },
      { role: "assistant", content: "I have memory_search and memory_get tools. The other tools are not exposed in this session." },
      { role: "user", content: "My name is Kartik" },
      { role: "assistant", content: "Got it, I'll remember that!" },
    ];

    const filtered = filterMessagesForExtraction(messages);

    // Should keep the name statement, filter the tool discussion
    expect(filtered.some(m => m.content.includes("Kartik"))).toBe(true);
    expect(filtered.some(m => m.content.includes("not exposed in this session"))).toBe(false);
  });

  it("keeps valuable user facts", () => {
    const messages = [
      { role: "user", content: "I prefer dark mode and use VS Code for development." },
      { role: "assistant", content: "Noted! Dark mode in VS Code is great for reducing eye strain." },
    ];

    const filtered = filterMessagesForExtraction(messages);
    expect(filtered.length).toBe(2);
    expect(filtered[0].content).toContain("dark mode");
  });
});
