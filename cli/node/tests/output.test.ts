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
  sanitizeAgentData,
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

  it("deduplicates PENDING entries with same event_id", () => {
    formatAddResult({
      results: [
        { status: "PENDING", event_id: "evt-dup" },
        { status: "PENDING", event_id: "evt-dup" },
      ],
    });
    // Should show only one PENDING block despite two entries with same event_id
    expect(output.match(/Queued/g)?.length).toBe(1);
    expect(output.match(/evt-dup/g)?.length).toBe(2); // event_id line + status hint line
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

describe("sanitizeAgentData", () => {
  it("projects add results", () => {
    const raw = [{ id: "abc", memory: "test", event: "ADD", metadata: { x: 1 }, categories: ["a"] }];
    const result = sanitizeAgentData("add", raw) as Record<string, unknown>[];
    expect(result).toEqual([{ id: "abc", memory: "test", event: "ADD" }]);
  });

  it("passes through PENDING add items", () => {
    const raw = [{ status: "PENDING", event_id: "evt-123", noise: "x" }];
    const result = sanitizeAgentData("add", raw) as Record<string, unknown>[];
    expect(result).toEqual([{ status: "PENDING", event_id: "evt-123" }]);
  });

  it("projects search results", () => {
    const raw = [{ id: "abc", memory: "test", score: 0.9, created_at: "2026-01-01", categories: ["a"], user_id: "u1" }];
    const result = sanitizeAgentData("search", raw) as Record<string, unknown>[];
    expect(result[0]).not.toHaveProperty("user_id");
    expect(result[0]).toHaveProperty("score");
  });

  it("projects list results", () => {
    const raw = [{ id: "abc", memory: "test", created_at: "2026-01-01", categories: ["a"], user_id: "u1" }];
    const result = sanitizeAgentData("list", raw) as Record<string, unknown>[];
    expect(Object.keys(result[0]).sort()).toEqual(["categories", "created_at", "id", "memory"]);
  });

  it("projects get result", () => {
    const raw = { id: "abc", memory: "test", created_at: "2026-01-01", updated_at: "2026-01-02", categories: ["a"], metadata: { k: "v" }, user_id: "u1" };
    const result = sanitizeAgentData("get", raw) as Record<string, unknown>;
    expect(result).not.toHaveProperty("user_id");
    expect(result).toHaveProperty("metadata");
  });

  it("projects update result", () => {
    const raw = { id: "abc", memory: "updated", extra: "noise" };
    const result = sanitizeAgentData("update", raw);
    expect(result).toEqual({ id: "abc", memory: "updated" });
  });

  it("projects event list results", () => {
    const raw = [{ id: "evt-1", event_type: "ADD", status: "SUCCEEDED", graph_status: null, latency: 100, created_at: "2026-01-01", updated_at: "2026-01-02" }];
    const result = sanitizeAgentData("event list", raw) as Record<string, unknown>[];
    expect(result[0]).not.toHaveProperty("updated_at");
    expect(result[0]).not.toHaveProperty("graph_status");
  });

  it("flattens event status results", () => {
    const raw = {
      id: "evt-1", event_type: "ADD", status: "SUCCEEDED",
      latency: 100, created_at: "2026-01-01", updated_at: "2026-01-02",
      results: [{ id: "mem-1", event: "ADD", user_id: "alice", data: { memory: "dark mode" } }],
    };
    const result = sanitizeAgentData("event status", raw) as Record<string, unknown>;
    const firstResult = (result.results as Record<string, unknown>[])[0];
    expect(firstResult).toHaveProperty("memory", "dark mode");
    expect(firstResult).not.toHaveProperty("data");
  });

  it("passes through status/config/import commands unchanged", () => {
    const data = { key: "value", other: "stuff" };
    for (const cmd of ["status", "import", "config show", "config get", "config set"]) {
      expect(sanitizeAgentData(cmd, data)).toEqual(data);
    }
  });

  it("handles null data", () => {
    expect(sanitizeAgentData("add", null)).toBeNull();
  });
});
