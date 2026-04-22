/**
 * Tests for CLI commands using mock backend.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createMockBackend } from "./setup.js";
import type { Backend } from "../src/backend/base.js";
import { setAgentMode } from "../src/state.js";

let mockBackend: Backend;

// Capture console.log and console.error output
let output: string;
let errOutput: string;
const originalLog = console.log;
const originalError = console.error;

beforeEach(() => {
  mockBackend = createMockBackend();
  output = "";
  errOutput = "";
  console.log = (...args: unknown[]) => {
    output += args.map(String).join(" ") + "\n";
  };
  console.error = (...args: unknown[]) => {
    errOutput += args.map(String).join(" ") + "\n";
  };
});

// Restore after each test
import { afterEach } from "vitest";
afterEach(() => {
  console.log = originalLog;
  console.error = originalError;
  setAgentMode(false);
});

describe("cmdAdd", () => {
  it("adds text memory", async () => {
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "I prefer dark mode", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "text",
    });
    expect(mockBackend.add).toHaveBeenCalledOnce();
  });

  it("adds from messages JSON", async () => {
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, undefined, {
      userId: "alice",
      messages: JSON.stringify([{ role: "user", content: "I love Python" }]),
      immutable: false,
      noInfer: false,

      output: "text",
    });
    expect(mockBackend.add).toHaveBeenCalledOnce();
  });

  it("outputs json format", async () => {
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "json",
    });
    expect(output).toContain("results");
  });

  it("quiet mode produces no memory content", async () => {
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "quiet",
    });
    expect(output).not.toContain("dark mode");
  });
});

describe("cmdAdd deduplicates PENDING", () => {
  const DUPLICATE_PENDING = {
    results: [
      { status: "PENDING", event_id: "evt-dup" },
      { status: "PENDING", event_id: "evt-dup" },
    ],
  };

  it("text shows one pending block", async () => {
    (mockBackend.add as ReturnType<typeof vi.fn>).mockResolvedValue(DUPLICATE_PENDING);
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "text",
    });
    expect(output.match(/Queued/g)?.length).toBe(1);
  });

  it("json shows one pending entry", async () => {
    (mockBackend.add as ReturnType<typeof vi.fn>).mockResolvedValue(DUPLICATE_PENDING);
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "json",
    });
    const data = JSON.parse(output);
    const pending = data.results.filter((r: Record<string, unknown>) => r.status === "PENDING");
    expect(pending).toHaveLength(1);
  });

  it("agent shows one pending entry", async () => {
    (mockBackend.add as ReturnType<typeof vi.fn>).mockResolvedValue(DUPLICATE_PENDING);
    setAgentMode(true);
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "agent",
    });
    const data = JSON.parse(output);
    expect(data.count).toBe(1);
    expect(data.data).toHaveLength(1);
  });
});

describe("cmdSearch", () => {
  it("searches and shows results in text mode", async () => {
    const { cmdSearch } = await import("../src/commands/memory.js");
    await cmdSearch(mockBackend, "preferences", {
      userId: "alice",
      topK: 10,
      threshold: 0.3,
      rerank: false,
      keyword: false,

      output: "text",
    });
    expect(output).toContain("Found 2");
  });

  it("outputs json format", async () => {
    const { cmdSearch } = await import("../src/commands/memory.js");
    await cmdSearch(mockBackend, "preferences", {
      userId: "alice",
      topK: 10,
      threshold: 0.3,
      rerank: false,
      keyword: false,

      output: "json",
    });
    expect(output).toContain("memory");
  });

  it("shows no results message", async () => {
    (mockBackend.search as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    const { cmdSearch } = await import("../src/commands/memory.js");
    await cmdSearch(mockBackend, "nonexistent", {
      userId: "alice",
      topK: 10,
      threshold: 0.3,
      rerank: false,
      keyword: false,

      output: "text",
    });
    expect(errOutput).toContain("No memories found");
  });
});

describe("cmdGet", () => {
  it("gets memory in text mode", async () => {
    const { cmdGet } = await import("../src/commands/memory.js");
    await cmdGet(mockBackend, "abc-123-def-456", { output: "text" });
    expect(output).toContain("dark mode");
  });

  it("gets memory in json mode", async () => {
    const { cmdGet } = await import("../src/commands/memory.js");
    await cmdGet(mockBackend, "abc-123-def-456", { output: "json" });
    expect(output).toContain("memory");
  });
});

describe("cmdList", () => {
  it("lists in table mode", async () => {
    const { cmdList } = await import("../src/commands/memory.js");
    await cmdList(mockBackend, {
      userId: "alice",
      page: 1,
      pageSize: 100,

      output: "table",
    });
    expect(output).toContain("dark mode");
  });

  it("shows empty message", async () => {
    (mockBackend.listMemories as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    const { cmdList } = await import("../src/commands/memory.js");
    await cmdList(mockBackend, {
      userId: "alice",
      page: 1,
      pageSize: 100,

      output: "text",
    });
    expect(errOutput).toContain("No memories found");
  });
});

describe("cmdUpdate", () => {
  it("updates memory", async () => {
    const { cmdUpdate } = await import("../src/commands/memory.js");
    await cmdUpdate(mockBackend, "abc-123", "New text", { output: "text" });
    expect(output.toLowerCase()).toContain("updated");
  });
});

describe("cmdDelete", () => {
  it("deletes memory", async () => {
    const { cmdDelete } = await import("../src/commands/memory.js");
    await cmdDelete(mockBackend, "abc-123", { output: "text" });
    expect(output.toLowerCase()).toContain("deleted");
  });
});

describe("cmdDeleteAll", () => {
  it("deletes all with force", async () => {
    const { cmdDeleteAll } = await import("../src/commands/memory.js");
    await cmdDeleteAll(mockBackend, {
      force: true,
      userId: "alice",
      output: "text",
    });
    expect(output.toLowerCase()).toContain("deleted");
  });
});


describe("cmdEntitiesList", () => {
  it("lists users in table mode", async () => {
    const { cmdEntitiesList } = await import("../src/commands/entities.js");
    await cmdEntitiesList(mockBackend, "users", { output: "table" });
    expect(output).toContain("alice");
  });

  it("lists in json mode", async () => {
    const { cmdEntitiesList } = await import("../src/commands/entities.js");
    await cmdEntitiesList(mockBackend, "users", { output: "json" });
    expect(output).toContain("alice");
  });
});

describe("cmdEventList", () => {
  it("lists events in table mode", async () => {
    const { cmdEventList } = await import("../src/commands/events.js");
    await cmdEventList(mockBackend, { output: "table" });
    expect(output).toContain("evt-abc-");
    expect(output).toContain("ADD");
    expect(output).toContain("SUCCEEDED");
  });

  it("lists events in json mode", async () => {
    const { cmdEventList } = await import("../src/commands/events.js");
    await cmdEventList(mockBackend, { output: "json" });
    expect(output).toContain("evt-abc-123-def-456");
    expect(output).toContain("evt-def-456-ghi-789");
  });

  it("shows empty message when no events", async () => {
    (mockBackend.listEvents as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);
    const { cmdEventList } = await import("../src/commands/events.js");
    await cmdEventList(mockBackend, { output: "table" });
    expect((output + errOutput).toLowerCase()).toContain("no events");
  });
});

describe("cmdEventStatus", () => {
  it("shows event details in text mode", async () => {
    const { cmdEventStatus } = await import("../src/commands/events.js");
    await cmdEventStatus(mockBackend, "evt-abc-123-def-456", { output: "text" });
    expect(output).toContain("evt-abc-123-def-456");
    expect(output).toContain("SUCCEEDED");
  });

  it("shows event details in json mode", async () => {
    const { cmdEventStatus } = await import("../src/commands/events.js");
    await cmdEventStatus(mockBackend, "evt-abc-123-def-456", { output: "json" });
    expect(output).toContain("evt-abc-123-def-456");
    expect(output).toContain("ADD");
  });
});

describe("agent mode", () => {
  it("cmdAdd outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "test preference", {
      userId: "alice",
      immutable: false,
      noInfer: false,

      output: "agent",
    });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("add");
    expect(parsed.data).toBeDefined();
    expect(parsed.scope).toMatchObject({ user_id: "alice" });
    expect(Object.keys(parsed.data[0]).sort()).toEqual(["event", "id", "memory"].sort());
  });

  it("cmdSearch outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdSearch } = await import("../src/commands/memory.js");
    await cmdSearch(mockBackend, "preferences", {
      userId: "alice",
      topK: 10,
      threshold: 0.3,
      rerank: false,
      keyword: false,

      output: "agent",
    });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("search");
    expect(Array.isArray(parsed.data)).toBe(true);
    expect(parsed.count).toBe(2);
    const keys = Object.keys(parsed.data[0]);
    expect(keys).toContain("id");
    expect(keys).toContain("memory");
    expect(keys).toContain("score");
    expect(keys).toContain("created_at");
    expect(keys).toContain("categories");
    expect(keys).not.toContain("user_id");
    expect(keys).not.toContain("agent_id");
  });

  it("cmdList outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdList } = await import("../src/commands/memory.js");
    await cmdList(mockBackend, {
      userId: "alice",
      page: 1,
      pageSize: 100,

      output: "agent",
    });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("list");
    expect(Array.isArray(parsed.data)).toBe(true);
    expect(parsed.count).toBe(2);
    expect(Object.keys(parsed.data[0]).sort()).toEqual(["categories", "created_at", "id", "memory"]);
  });

  it("cmdGet outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdGet } = await import("../src/commands/memory.js");
    await cmdGet(mockBackend, "abc-123-def-456", { output: "agent" });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("get");
    expect(parsed.data).toBeDefined();
    expect(parsed.data).toMatchObject({ id: "abc-123-def-456" });
    expect(Object.keys(parsed.data)).not.toContain("user_id");
  });

  it("cmdUpdate outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdUpdate } = await import("../src/commands/memory.js");
    await cmdUpdate(mockBackend, "abc-123", "Updated text", { output: "agent" });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("update");
    expect(parsed.data).toBeDefined();
  });

  it("cmdDelete outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdDelete } = await import("../src/commands/memory.js");
    await cmdDelete(mockBackend, "abc-123", { output: "agent" });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("delete");
    expect(parsed.data).toBeDefined();
  });

  it("cmdEventList outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdEventList } = await import("../src/commands/events.js");
    await cmdEventList(mockBackend, { output: "agent" });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("event list");
    expect(Array.isArray(parsed.data)).toBe(true);
    expect(parsed.count).toBe(2);
    expect(Object.keys(parsed.data[0]).sort()).toEqual(
      ["created_at", "event_type", "id", "latency", "status"],
    );
    expect(Object.keys(parsed.data[0])).not.toContain("updated_at");
  });

  it("cmdEventStatus outputs JSON envelope", async () => {
    setAgentMode(true);
    const { cmdEventStatus } = await import("../src/commands/events.js");
    await cmdEventStatus(mockBackend, "evt-abc-123-def-456", { output: "agent" });
    const parsed = JSON.parse(output.trim());
    expect(parsed.status).toBe("success");
    expect(parsed.command).toBe("event status");
    expect(parsed.data).toBeDefined();
    expect(parsed.data).toMatchObject({ id: "evt-abc-123-def-456" });
    expect(parsed.data.results[0]).toHaveProperty("memory");
    expect(parsed.data.results[0]).not.toHaveProperty("data");
  });
});
