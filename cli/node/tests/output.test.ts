/**
 * Tests for output formatting.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  formatMemoriesText,
  formatMemoriesTable,
  formatJson,
  formatSingleMemory,
  formatAddResult,
  printResultSummary,
} from "../src/output.js";

let output: string;
const originalLog = console.log;

beforeEach(() => {
  output = "";
  console.log = (...args: unknown[]) => {
    output += args.map(String).join(" ") + "\n";
  };
});

afterEach(() => {
  console.log = originalLog;
});

const sampleMemories = [
  {
    id: "abc-123-def-456",
    memory: "User prefers dark mode",
    score: 0.92,
    created_at: "2026-02-15T10:30:00Z",
    categories: ["preferences"],
  },
  {
    id: "ghi-789-jkl-012",
    memory: "User uses vim keybindings",
    score: 0.78,
    created_at: "2026-03-01T14:00:00Z",
    categories: ["tools"],
  },
];

describe("formatMemoriesText", () => {
  it("shows count and memory content", () => {
    formatMemoriesText(sampleMemories);
    expect(output).toContain("Found 2");
    expect(output).toContain("dark mode");
    expect(output).toContain("vim keybindings");
  });

  it("shows scores and IDs", () => {
    formatMemoriesText(sampleMemories);
    expect(output).toContain("0.92");
    expect(output).toContain("abc-123-");
  });
});

describe("formatMemoriesTable", () => {
  it("renders a table with memory content", () => {
    formatMemoriesTable(sampleMemories);
    expect(output).toContain("dark mode");
  });
});

describe("formatJson", () => {
  it("outputs valid JSON", () => {
    formatJson({ key: "value" });
    expect(JSON.parse(output)).toEqual({ key: "value" });
  });
});

describe("formatSingleMemory", () => {
  it("shows memory text in text mode", () => {
    formatSingleMemory(sampleMemories[0], "text");
    expect(output).toContain("dark mode");
  });

  it("outputs JSON in json mode", () => {
    formatSingleMemory(sampleMemories[0], "json");
    expect(output).toContain("memory");
  });
});

describe("formatAddResult", () => {
  it("shows ADD event", () => {
    formatAddResult({
      results: [{ id: "abc-123", memory: "Test", event: "ADD" }],
    });
    expect(output).toContain("Added");
  });

  it("shows PENDING event", () => {
    formatAddResult({
      results: [{ status: "PENDING", event_id: "evt-12345678" }],
    });
    expect(output).toContain("Queued");
  });
});

describe("printResultSummary", () => {
  it("shows count and duration", () => {
    printResultSummary({ count: 5, durationSecs: 1.23 });
    expect(output).toContain("5 results");
    expect(output).toContain("1.23s");
  });

  it("handles singular", () => {
    printResultSummary({ count: 1 });
    expect(output).toContain("1 result");
    expect(output).not.toContain("results");
  });
});
