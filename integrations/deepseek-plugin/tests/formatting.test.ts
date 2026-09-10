import { describe, it, expect } from "vitest";
import {
  formatAge,
  formatMemoryCompact,
  formatMemoryList,
  formatAddResult,
} from "../src/formatting.ts";

describe("formatAge", () => {
  it("formats minutes, hours, and days", () => {
    expect(formatAge(new Date(Date.now() - 30 * 60_000))).toBe("30m ago");
    expect(formatAge(new Date(Date.now() - 3 * 3_600_000))).toBe("3h ago");
    expect(formatAge(new Date(Date.now() - 5 * 86_400_000))).toBe("5d ago");
  });
});

describe("formatMemoryCompact", () => {
  it("renders one line with category, text, and id", () => {
    const line = formatMemoryCompact({
      id: "abc-123",
      memory: "User prefers dark mode",
      categories: ["preference"],
      createdAt: new Date(),
    });
    expect(line).toContain("[preference]");
    expect(line).toContain("User prefers dark mode");
    expect(line).toContain("[mem0:abc-123]");
  });

  it("falls back to uncategorized and (empty)", () => {
    expect(formatMemoryCompact({ id: "x" })).toContain("[uncategorized]");
    expect(formatMemoryCompact({ id: "x" })).toContain("(empty)");
  });
});

describe("formatMemoryList", () => {
  it("numbers multiple memories", () => {
    const output = formatMemoryList([
      { id: "id-1", memory: "Fact one", categories: ["insight"] },
      { id: "id-2", memory: "Fact two", categories: ["convention"] },
    ]);
    expect(output).toContain("1.");
    expect(output).toContain("2.");
  });

  it("returns a plain message when there are no memories", () => {
    expect(formatMemoryList([])).toBe("No memories found.");
  });
});

describe("formatAddResult", () => {
  it("reports queued for the async PENDING response, with the event id", () => {
    // SDK camel-cases response keys, so the real shape is `eventId`.
    const out = formatAddResult({ eventId: "evt-9", status: "PENDING" });
    expect(out).toContain("queued");
    expect(out).toContain("evt-9");
  });

  it("reports the stored count when the backend returns memories", () => {
    expect(formatAddResult([{ id: "1", memory: "A" }])).toContain("Stored 1 memory");
    expect(formatAddResult([{ id: "1" }, { id: "2" }])).toContain("Stored 2 memories");
  });

  it("unwraps a { results: [...] } envelope", () => {
    expect(formatAddResult({ results: [{ id: "1", memory: "A" }] })).toContain("Stored 1 memory");
  });

  it("handles an empty result", () => {
    expect(formatAddResult([])).toBe("Memory stored.");
  });
});
