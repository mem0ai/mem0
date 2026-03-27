/**
 * Tests for CLI commands using mock backend.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createMockBackend } from "./setup.js";
import type { Backend } from "../src/backend/base.js";

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
});

describe("cmdAdd", () => {
  it("adds text memory", async () => {
    const { cmdAdd } = await import("../src/commands/memory.js");
    await cmdAdd(mockBackend, "I prefer dark mode", {
      userId: "alice",
      immutable: false,
      noInfer: false,
      enableGraph: false,
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
      enableGraph: false,
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
      enableGraph: false,
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
      enableGraph: false,
      output: "quiet",
    });
    expect(output).not.toContain("dark mode");
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
      enableGraph: false,
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
      enableGraph: false,
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
      enableGraph: false,
      output: "text",
    });
    expect(output).toContain("No memories found");
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
      enableGraph: false,
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
      enableGraph: false,
      output: "text",
    });
    expect(output).toContain("No memories found");
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

describe("cmdVersion", () => {
  it("shows version", async () => {
    const { cmdVersion } = await import("../src/commands/utils.js");
    cmdVersion();
    expect(output).toContain("0.1.0");
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
