import { describe, it, expect } from "vitest";
import { formatAge, formatMemoryCompact, formatMemoryList } from "../src/memory/formatting.ts";

describe("formatAge", () => {
  it("formats minutes", () => {
    expect(formatAge(new Date(Date.now() - 30 * 60_000))).toBe("30m ago");
  });

  it("formats hours", () => {
    expect(formatAge(new Date(Date.now() - 3 * 3_600_000))).toBe("3h ago");
  });

  it("formats days", () => {
    expect(formatAge(new Date(Date.now() - 5 * 86_400_000))).toBe("5d ago");
  });
});

describe("formatMemoryCompact", () => {
  it("formats a memory as a single line", () => {
    const mem = {
      id: "abc-123-def-456",
      memory: "User prefers dark mode",
      categories: ["preference"],
      createdAt: new Date(),
    };
    const line = formatMemoryCompact(mem);
    expect(line).toContain("[preference]");
    expect(line).toContain("User prefers dark mode");
    expect(line).toContain("[mem0:abc-123-def-456]");
  });
});

describe("formatMemoryList", () => {
  it("formats multiple memories with numbering", () => {
    const memories = [
      { id: "id-1", memory: "Fact one", categories: ["insight"], createdAt: new Date() },
      { id: "id-2", memory: "Fact two", categories: ["convention"], createdAt: new Date() },
    ];
    const output = formatMemoryList(memories);
    expect(output).toContain("1.");
    expect(output).toContain("2.");
  });

  it("returns empty message for no memories", () => {
    expect(formatMemoryList([])).toBe("No memories found.");
  });
});
