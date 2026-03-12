import { formatMessagesWithRoles } from "../src/utils/formatMessages";
import type { Message } from "../src/types";

describe("formatMessagesWithRoles", () => {
  it("uses default role labels when no roleNames provided", () => {
    const messages: Message[] = [
      { role: "user", content: "hi" },
      { role: "assistant", content: "hello" },
    ];
    expect(formatMessagesWithRoles(messages)).toBe(
      "user: hi\nassistant: hello",
    );
  });

  it("maps roles to custom names", () => {
    const messages: Message[] = [
      { role: "user", content: "How are you?" },
      { role: "assistant", content: "I'm good!" },
    ];
    const result = formatMessagesWithRoles(messages, {
      user: "Thomas",
      assistant: "Kite",
    });
    expect(result).toBe("Thomas: How are you?\nKite: I'm good!");
  });

  it("preserves system role as-is", () => {
    const messages: Message[] = [
      { role: "system", content: "You are helpful" },
      { role: "user", content: "hi" },
    ];
    const result = formatMessagesWithRoles(messages, {
      user: "Thomas",
      assistant: "Kite",
    });
    expect(result).toBe("system: You are helpful\nThomas: hi");
  });

  it("returns empty string for empty messages", () => {
    expect(formatMessagesWithRoles([])).toBe("");
  });

  it("filters out non-string content (multimodal messages)", () => {
    const messages: Message[] = [
      { role: "user", content: "hello" },
      {
        role: "user",
        content: { type: "image_url", image_url: { url: "http://img" } } as any,
      },
      { role: "assistant", content: "I see" },
    ];
    expect(formatMessagesWithRoles(messages)).toBe(
      "user: hello\nassistant: I see",
    );
  });

  it("falls back to raw role string for unknown roles", () => {
    const messages: Message[] = [{ role: "tool", content: "result data" }];
    expect(formatMessagesWithRoles(messages)).toBe("tool: result data");
  });

  it("applies partial roleNames (only user provided)", () => {
    const messages: Message[] = [
      { role: "user", content: "hey" },
      { role: "assistant", content: "yo" },
    ];
    const result = formatMessagesWithRoles(messages, { user: "Thomas" });
    expect(result).toBe("Thomas: hey\nassistant: yo");
  });
});
