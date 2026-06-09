import { describe, it, expect, vi } from "vitest";
import { buildToolExecute } from "../src/memory/tools.ts";
import type { ScopeContext } from "../src/types.ts";

const mockMem0 = {
  search: vi.fn(),
  add: vi.fn(),
  getAll: vi.fn(),
  delete: vi.fn(),
  deleteAll: vi.fn(),
};

const scopeCtx: ScopeContext = {
  userId: "testuser",
  appId: "testproject",
  runId: "session123",
};

describe("buildToolExecute", () => {
  const execute = buildToolExecute(mockMem0 as any, scopeCtx, "project");

  it("search calls mem0.search with correct filters", async () => {
    mockMem0.search.mockResolvedValue({ results: [] });
    await execute({ action: "search", query: "dark mode" });
    expect(mockMem0.search).toHaveBeenCalledWith("dark mode", {
      filters: { user_id: "testuser", app_id: "testproject" },
    });
  });

  it("add calls mem0.add with customCategories and entity params", async () => {
    mockMem0.add.mockResolvedValue([{ id: "new-id", memory: "test" }]);
    await execute({ action: "add", content: "User likes tabs" });
    const call = mockMem0.add.mock.calls[0];
    expect(call[0]).toEqual([{ role: "user", content: "User likes tabs" }]);
    expect(call[1].userId).toBe("testuser");
    expect(call[1].appId).toBe("testproject");
    expect(call[1].customCategories).toBeDefined();
    expect(call[1].customCategories.length).toBe(10);
  });

  it("search with scope=global filters by user_id with app_id wildcard", async () => {
    mockMem0.search.mockResolvedValue({ results: [] });
    await execute({ action: "search", query: "preferences", scope: "global" });
    expect(mockMem0.search).toHaveBeenCalledWith("preferences", {
      filters: { user_id: "testuser", app_id: "*" },
    });
  });

  it("delete calls mem0.delete with memory_id", async () => {
    mockMem0.delete.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete", memory_id: "abc-123" });
    expect(mockMem0.delete).toHaveBeenCalledWith("abc-123");
  });
});
