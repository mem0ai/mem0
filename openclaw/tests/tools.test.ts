/**
 * Tests for the tool factory functions in tools/.
 *
 * Verifies each factory returns the expected shape (name, label,
 * description, parameters, execute) and that execute() delegates
 * to the correct provider/backend methods.
 */
import { describe, it, expect, vi } from "vitest";

import type { ToolDeps } from "../tools/index.ts";
import { registerAllTools } from "../tools/index.ts";
import { createMemorySearchTool } from "../tools/memory-search.ts";
import { createMemoryAddTool } from "../tools/memory-add.ts";
import { createMemoryGetTool } from "../tools/memory-get.ts";
import { createMemoryDeleteTool } from "../tools/memory-delete.ts";
import { createMemoryListTool } from "../tools/memory-list.ts";
import { createMemoryUpdateTool } from "../tools/memory-update.ts";
import { createMemoryEventListTool } from "../tools/memory-event-list.ts";
import { createMemoryEventStatusTool } from "../tools/memory-event-status.ts";

// ---------------------------------------------------------------------------
// Mock helper
// ---------------------------------------------------------------------------

function createMockToolDeps(overrides = {}): ToolDeps {
  return {
    api: {
      registerTool: vi.fn(),
      logger: { info: vi.fn(), warn: vi.fn() },
    } as any,
    cfg: {
      mode: "platform",
      userId: "testuser",
      topK: 5,
      autoCapture: true,
      autoRecall: true,
      searchThreshold: 0.5,
      customInstructions: "test",
      customCategories: {},
    } as any,
    provider: {
      search: vi
        .fn()
        .mockResolvedValue([{ id: "m1", memory: "test memory", score: 0.9 }]),
      add: vi.fn().mockResolvedValue({
        results: [{ event: "ADD", memory: "stored" }],
      }),
      getAll: vi.fn().mockResolvedValue([{ id: "m1", memory: "test memory" }]),
      update: vi.fn().mockResolvedValue({ memory: "updated" }),
      delete: vi.fn().mockResolvedValue(undefined),
      deleteAll: vi.fn().mockResolvedValue(undefined),
      get: vi.fn().mockResolvedValue({
        id: "test-id",
        memory: "test memory",
        created_at: "2026-01-01",
        updated_at: "2026-01-02",
      }),
      history: vi.fn().mockResolvedValue([]),
      getHistory: vi.fn().mockResolvedValue([]),
    } as any,
    resolveUserId: vi.fn().mockReturnValue("testuser"),
    effectiveUserId: vi.fn().mockReturnValue("testuser"),
    agentUserId: vi.fn().mockReturnValue("testuser:agent:test"),
    getCurrentSessionId: vi.fn().mockReturnValue(undefined),
    skillsActive: false,
    captureToolEvent: vi.fn(),
    buildAddOptions: vi
      .fn()
      .mockReturnValue({ user_id: "testuser", source: "OPENCLAW" }),
    buildSearchOptions: vi
      .fn()
      .mockReturnValue({ user_id: "testuser", top_k: 5, source: "OPENCLAW" }),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// registerAllTools
// ---------------------------------------------------------------------------

describe("registerAllTools", () => {
  it("calls api.registerTool exactly 8 times", () => {
    const ctx = createMockToolDeps();
    registerAllTools(ctx);
    expect(ctx.api.registerTool).toHaveBeenCalledTimes(8);
  });

  it("registers tools with the correct names", () => {
    const ctx = createMockToolDeps();
    registerAllTools(ctx);

    // Tools are registered as required (single argument — no metadata object).
    // The name comes from the tool definition itself (call[0]).
    const names = (
      ctx.api.registerTool as ReturnType<typeof vi.fn>
    ).mock.calls.map((call: unknown[]) => (call[0] as { name: string }).name);

    expect(names).toEqual([
      "memory_search",
      "memory_add",
      "memory_get",
      "memory_list",
      "memory_update",
      "memory_delete",
      "memory_event_list",
      "memory_event_status",
    ]);
  });

  it("registers tools with optional: false metadata", () => {
    const ctx = createMockToolDeps();
    registerAllTools(ctx);

    const calls = (ctx.api.registerTool as ReturnType<typeof vi.fn>).mock.calls;
    for (const call of calls) {
      expect(call).toHaveLength(2);
      expect(call[1]).toEqual({ optional: false });
    }
  });
});

// ---------------------------------------------------------------------------
// Tool factory shape checks
// ---------------------------------------------------------------------------

describe("tool factory shape", () => {
  const factories = [
    { fn: createMemorySearchTool, expectedName: "memory_search" },
    { fn: createMemoryAddTool, expectedName: "memory_add" },
    { fn: createMemoryGetTool, expectedName: "memory_get" },
    { fn: createMemoryDeleteTool, expectedName: "memory_delete" },
    { fn: createMemoryListTool, expectedName: "memory_list" },
    { fn: createMemoryEventListTool, expectedName: "memory_event_list" },
    { fn: createMemoryEventStatusTool, expectedName: "memory_event_status" },
  ];

  for (const { fn, expectedName } of factories) {
    describe(expectedName, () => {
      it("returns an object with name, label, description, parameters, and execute", () => {
        const ctx = createMockToolDeps();
        const tool = fn(ctx);

        expect(tool.name).toBe(expectedName);
        expect(typeof tool.label).toBe("string");
        expect(tool.label.length).toBeGreaterThan(0);
        expect(typeof tool.description).toBe("string");
        expect(tool.description.length).toBeGreaterThan(0);
        expect(tool.parameters).toBeDefined();
        expect(typeof tool.execute).toBe("function");
      });
    });
  }
});

// ---------------------------------------------------------------------------
// memory_search execute
// ---------------------------------------------------------------------------

describe("memory_search execute", () => {
  it("returns formatted results when provider returns matches", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemorySearchTool(ctx);

    const result = await tool.execute("call-1", {
      query: "user preferences",
    });

    expect(ctx.provider!.search).toHaveBeenCalled();
    expect(result.content[0].text).toContain("Found 1 memories");
    expect(result.content[0].text).toContain("test memory");
    expect(result.content[0].text).toContain("90%");
    expect(result.details.count).toBe(1);
    expect(result.details.memories).toHaveLength(1);
    expect(result.details.memories[0].id).toBe("m1");
  });

  it("returns 'no relevant memories' when provider returns empty", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn().mockResolvedValue([]),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemorySearchTool(ctx);

    const result = await tool.execute("call-2", { query: "nothing" });

    expect(result.content[0].text).toBe("No relevant memories found.");
    expect(result.details.count).toBe(0);
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn().mockRejectedValue(new Error("network failure")),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemorySearchTool(ctx);

    const result = await tool.execute("call-3", { query: "test" });

    expect(result.content[0].text).toContain("Memory search failed");
    expect(result.content[0].text).toContain("network failure");
    expect(result.details.error).toContain("network failure");
  });

  it("calls resolveUserId with provided agentId and userId", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemorySearchTool(ctx);

    await tool.execute("call-4", {
      query: "test",
      agentId: "researcher",
      userId: "alice",
    });

    expect(ctx.resolveUserId).toHaveBeenCalledWith({
      agentId: "researcher",
      userId: "alice",
    });
  });

  it("passes limit to buildSearchOptions", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemorySearchTool(ctx);

    await tool.execute("call-5", { query: "test", limit: 10 });

    expect(ctx.buildSearchOptions).toHaveBeenCalledWith("testuser", 10);
  });

  it("searches only session scope when scope='session' and session exists", async () => {
    const searchMock = vi
      .fn()
      .mockResolvedValue([{ id: "s1", memory: "session mem", score: 0.8 }]);
    const ctx = createMockToolDeps({
      getCurrentSessionId: vi.fn().mockReturnValue("session-abc"),
      provider: {
        search: searchMock,
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemorySearchTool(ctx);

    const result = await tool.execute("call-6", {
      query: "test",
      scope: "session",
    });

    // Should call buildSearchOptions with session ID as 4th arg (sessionKey)
    expect(ctx.buildSearchOptions).toHaveBeenCalledWith(
      "testuser",
      undefined,
      undefined,
      "session-abc",
    );
    expect(result.details.count).toBe(1);
  });

  it("deduplicates results in 'all' scope", async () => {
    const searchMock = vi
      .fn()
      // First call: long-term
      .mockResolvedValueOnce([
        { id: "m1", memory: "shared memory", score: 0.95 },
      ])
      // Second call: session
      .mockResolvedValueOnce([
        { id: "m1", memory: "shared memory", score: 0.85 },
        { id: "m2", memory: "session only", score: 0.7 },
      ]);

    const ctx = createMockToolDeps({
      getCurrentSessionId: vi.fn().mockReturnValue("session-xyz"),
      provider: {
        search: searchMock,
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemorySearchTool(ctx);

    const result = await tool.execute("call-7", {
      query: "test",
      scope: "all",
    });

    // m1 appears only once (from long-term), m2 is session-only
    expect(result.details.count).toBe(2);
    const ids = result.details.memories.map((m: any) => m.id);
    expect(ids).toEqual(["m1", "m2"]);
  });
});

// ---------------------------------------------------------------------------
// memory_add execute
// ---------------------------------------------------------------------------

describe("memory_add execute", () => {
  it("calls provider.add with the text and returns stored result", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-1", {
      text: "User prefers dark mode",
    });

    expect(ctx.provider!.add).toHaveBeenCalled();
    const addCall = (ctx.provider!.add as ReturnType<typeof vi.fn>).mock
      .calls[0];
    expect(addCall[0]).toEqual([
      { role: "user", content: "User prefers dark mode" },
    ]);
    expect(result.content[0].text).toContain("Stored");
    expect(result.details.action).toBe("stored");
  });

  it("returns error when no text or facts are provided", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-2", {});

    expect(result.content[0].text).toContain("No facts provided");
    expect(result.details.error).toBe("missing_facts");
  });

  it("supports facts array", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-3", {
      facts: ["fact one", "fact two"],
    });

    expect(ctx.provider!.add).toHaveBeenCalled();
    const addCall = (ctx.provider!.add as ReturnType<typeof vi.fn>).mock
      .calls[0];
    expect(addCall[0]).toEqual([
      { role: "user", content: "fact one\nfact two" },
    ]);
    expect(result.details.action).toBe("stored");
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn().mockResolvedValue([]),
        add: vi.fn().mockRejectedValue(new Error("API error")),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-4", { text: "test" });

    expect(result.content[0].text).toContain("Memory add failed");
    expect(result.details.error).toContain("API error");
  });

  it("uses skills mode with infer=false when skillsActive is true", async () => {
    const addMock = vi.fn().mockResolvedValue({
      results: [{ event: "ADD", memory: "stored in skills mode" }],
    });
    const ctx = createMockToolDeps({
      skillsActive: true,
      provider: {
        search: vi.fn().mockResolvedValue([]),
        add: addMock,
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-5", {
      text: "skills fact",
      category: "preference",
    });

    expect(addMock).toHaveBeenCalledOnce();
    const addOpts = addMock.mock.calls[0][1];
    expect(addOpts.infer).toBe(false);
    expect(result.details.mode).toBe("skills");
    expect(result.details.category).toBe("preference");
  });

  it("blocks subagent sessions from storing", async () => {
    const ctx = createMockToolDeps({
      getCurrentSessionId: vi
        .fn()
        .mockReturnValue("agent:main:subagent:uuid-123"),
    });
    const tool = createMemoryAddTool(ctx);

    const result = await tool.execute("call-6", { text: "subagent fact" });

    expect(ctx.provider!.add).not.toHaveBeenCalled();
    expect(result.details.error).toBe("subagent_blocked");
  });

  it("performs dedup search before adding in legacy mode", async () => {
    const searchMock = vi.fn().mockResolvedValue([]);
    const addMock = vi.fn().mockResolvedValue({
      results: [{ event: "ADD", memory: "stored" }],
    });
    const ctx = createMockToolDeps({
      skillsActive: false,
      provider: {
        search: searchMock,
        add: addMock,
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryAddTool(ctx);

    await tool.execute("call-7", { text: "new fact" });

    // Mem0 backend handles dedup internally — no separate search call
    expect(searchMock).not.toHaveBeenCalled();
    expect(addMock).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// memory_get execute
// ---------------------------------------------------------------------------

describe("memory_get execute", () => {
  it("calls provider.get with the memoryId and returns formatted result", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryGetTool(ctx);

    const result = await tool.execute("call-1", { memoryId: "test-id" });

    expect(ctx.provider!.get).toHaveBeenCalledWith("test-id");
    expect(result.content[0].text).toContain("Memory test-id");
    expect(result.content[0].text).toContain("test memory");
    expect(result.content[0].text).toContain("Created:");
    expect(result.details.memory).toBeDefined();
    expect(result.details.memory.id).toBe("test-id");
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn().mockRejectedValue(new Error("not found")),
        history: vi.fn(),
      },
    });
    const tool = createMemoryGetTool(ctx);

    const result = await tool.execute("call-2", { memoryId: "bad-id" });

    expect(result.content[0].text).toContain("Memory get failed");
    expect(result.details.error).toContain("not found");
  });
});

// ---------------------------------------------------------------------------
// memory_delete execute
// ---------------------------------------------------------------------------

describe("memory_delete execute", () => {
  it("deletes by memoryId via provider.delete", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-1", { memoryId: "mem-abc" });

    expect(ctx.provider!.delete).toHaveBeenCalledWith("mem-abc");
    expect(result.content[0].text).toBe("Memory mem-abc deleted.");
    expect(result.details.action).toBe("deleted");
    expect(result.details.id).toBe("mem-abc");
  });

  it("searches and auto-deletes single high-confidence match by query", async () => {
    const searchMock = vi
      .fn()
      .mockResolvedValue([{ id: "m1", memory: "match", score: 0.95 }]);
    const deleteMock = vi.fn().mockResolvedValue(undefined);
    const ctx = createMockToolDeps({
      provider: {
        search: searchMock,
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: deleteMock,
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-2", {
      query: "find and delete",
    });

    expect(searchMock).toHaveBeenCalled();
    expect(deleteMock).toHaveBeenCalledWith("m1");
    expect(result.content[0].text).toContain("Deleted:");
    expect(result.details.action).toBe("deleted");
  });

  it("returns candidates when query matches multiple ambiguous results", async () => {
    const searchMock = vi.fn().mockResolvedValue([
      { id: "m1", memory: "candidate one", score: 0.7 },
      { id: "m2", memory: "candidate two", score: 0.6 },
    ]);
    const deleteMock = vi.fn();
    const ctx = createMockToolDeps({
      provider: {
        search: searchMock,
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: deleteMock,
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-3", {
      query: "ambiguous",
    });

    // Should NOT have called delete
    expect(deleteMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("Found 2 candidates");
    expect(result.details.action).toBe("candidates");
    expect(result.details.candidates).toHaveLength(2);
  });

  it("returns no matching memories when query yields empty results", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn().mockResolvedValue([]),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-4", { query: "nothing" });

    expect(result.content[0].text).toBe("No matching memories found.");
    expect(result.details.found).toBe(0);
  });

  it("requires confirm:true for bulk delete (all)", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-5", { all: true });

    expect(result.content[0].text).toContain("confirm: true");
    expect(result.details.error).toBe("confirmation_required");
  });

  it("performs bulk delete when all:true and confirm:true", async () => {
    const deleteAllMock = vi.fn().mockResolvedValue(undefined);
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn(),
        deleteAll: deleteAllMock,
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-6", {
      all: true,
      confirm: true,
    });

    expect(deleteAllMock).toHaveBeenCalledWith("testuser");
    expect(result.content[0].text).toContain("All memories deleted");
    expect(result.details.action).toBe("deleted_all");
  });

  it("returns error when no mode param is specified", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-9", {});

    expect(result.content[0].text).toContain(
      "Provide memoryId, query, or all:true",
    );
    expect(result.details.error).toBe("missing_param");
  });

  it("blocks subagent sessions from deleting", async () => {
    const ctx = createMockToolDeps({
      getCurrentSessionId: vi
        .fn()
        .mockReturnValue("agent:main:subagent:uuid-456"),
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-10", { memoryId: "m1" });

    expect(ctx.provider!.delete).not.toHaveBeenCalled();
    expect(result.details.error).toBe("subagent_blocked");
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn(),
        delete: vi.fn().mockRejectedValue(new Error("delete failed")),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryDeleteTool(ctx);

    const result = await tool.execute("call-11", { memoryId: "m1" });

    expect(result.content[0].text).toContain("Memory delete failed");
    expect(result.details.error).toContain("delete failed");
  });
});

// ---------------------------------------------------------------------------
// memory_list execute
// ---------------------------------------------------------------------------

describe("memory_list execute", () => {
  it("calls provider.getAll and returns formatted list", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryListTool(ctx);

    const result = await tool.execute("call-1", {});

    expect(ctx.provider!.getAll).toHaveBeenCalled();
    expect(result.content[0].text).toContain("1 memories");
    expect(result.content[0].text).toContain("test memory");
    expect(result.details.count).toBe(1);
    expect(result.details.memories).toHaveLength(1);
  });

  it("returns 'no memories stored' when provider returns empty", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn().mockResolvedValue([]),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryListTool(ctx);

    const result = await tool.execute("call-2", {});

    expect(result.content[0].text).toBe("No memories stored yet.");
    expect(result.details.count).toBe(0);
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn().mockRejectedValue(new Error("list failed")),
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryListTool(ctx);

    const result = await tool.execute("call-3", {});

    expect(result.content[0].text).toContain("Memory list failed");
    expect(result.details.error).toContain("list failed");
  });

  it("resolves userId from agentId", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryListTool(ctx);

    await tool.execute("call-4", { agentId: "researcher" });

    expect(ctx.resolveUserId).toHaveBeenCalledWith({
      agentId: "researcher",
      userId: undefined,
    });
  });

  it("deduplicates results in 'all' scope", async () => {
    const getAllMock = vi
      .fn()
      // First call: long-term
      .mockResolvedValueOnce([{ id: "m1", memory: "shared" }])
      // Second call: session
      .mockResolvedValueOnce([
        { id: "m1", memory: "shared" },
        { id: "m2", memory: "session only" },
      ]);

    const ctx = createMockToolDeps({
      getCurrentSessionId: vi.fn().mockReturnValue("session-123"),
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: getAllMock,
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryListTool(ctx);

    const result = await tool.execute("call-5", { scope: "all" });

    expect(result.details.count).toBe(2);
    const ids = result.details.memories.map((m: any) => m.id);
    expect(ids).toEqual(["m1", "m2"]);
  });

  it("only fetches session memories when scope='session'", async () => {
    const getAllMock = vi
      .fn()
      .mockResolvedValue([{ id: "s1", memory: "session mem" }]);
    const ctx = createMockToolDeps({
      getCurrentSessionId: vi.fn().mockReturnValue("sess-abc"),
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: getAllMock,
        update: vi.fn(),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryListTool(ctx);

    const result = await tool.execute("call-6", { scope: "session" });

    // Should call getAll once with run_id
    expect(getAllMock).toHaveBeenCalledOnce();
    const opts = getAllMock.mock.calls[0][0];
    expect(opts.run_id).toBe("sess-abc");
    expect(result.details.count).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// memory_update execute
// ---------------------------------------------------------------------------

describe("memory_update execute", () => {
  it("calls provider.update and returns success", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryUpdateTool(ctx);

    const result = await tool.execute("call-1", {
      memoryId: "mem-123",
      text: "Updated preference",
    });

    expect(ctx.provider!.update).toHaveBeenCalledWith(
      "mem-123",
      "Updated preference",
    );
    expect(result.content[0].text).toContain("Updated memory mem-123");
    expect(result.content[0].text).toContain("Updated preference");
    expect(result.details.action).toBe("updated");
    expect(result.details.id).toBe("mem-123");
  });

  it("truncates long text in response", async () => {
    const ctx = createMockToolDeps();
    const tool = createMemoryUpdateTool(ctx);

    const longText = "A".repeat(120);
    const result = await tool.execute("call-2", {
      memoryId: "mem-456",
      text: longText,
    });

    expect(ctx.provider!.update).toHaveBeenCalledWith("mem-456", longText);
    // The response text should contain the first 80 chars followed by "..."
    expect(result.content[0].text).toContain("A".repeat(80) + "...");
    expect(result.content[0].text).not.toContain("A".repeat(81));
    expect(result.details.action).toBe("updated");
  });

  it("blocks subagent sessions", async () => {
    const ctx = createMockToolDeps({
      getCurrentSessionId: vi
        .fn()
        .mockReturnValue("agent:main:subagent:uuid-789"),
    });
    const tool = createMemoryUpdateTool(ctx);

    const result = await tool.execute("call-3", {
      memoryId: "mem-123",
      text: "should not update",
    });

    expect(ctx.provider!.update).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain(
      "not available in subagent sessions",
    );
    expect(result.details.error).toBe("subagent_blocked");
  });

  it("handles errors gracefully", async () => {
    const ctx = createMockToolDeps({
      provider: {
        search: vi.fn(),
        add: vi.fn(),
        getAll: vi.fn(),
        update: vi.fn().mockRejectedValue(new Error("update conflict")),
        delete: vi.fn(),
        get: vi.fn(),
        history: vi.fn(),
      },
    });
    const tool = createMemoryUpdateTool(ctx);

    const result = await tool.execute("call-4", {
      memoryId: "mem-123",
      text: "new text",
    });

    expect(result.content[0].text).toContain("Memory update failed");
    expect(result.content[0].text).toContain("update conflict");
    expect(result.details.error).toContain("update conflict");
  });
});

