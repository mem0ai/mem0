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

  it("add with scope=global tags appId with the sentinel so it stays reachable by the global search wildcard", async () => {
    mockMem0.add.mockResolvedValue([{ id: "new-id", memory: "test" }]);
    await execute({ action: "add", content: "Cross-project preference", scope: "global" });
    const call = mockMem0.add.mock.calls[mockMem0.add.mock.calls.length - 1];
    expect(call[1].userId).toBe("testuser");
    // Literal, not the imported GLOBAL_APP_ID: without the fix the import is
    // undefined and so is call[1].appId, so toBe(GLOBAL_APP_ID) would pass on
    // exactly the code this test guards against.
    expect(call[1].appId).toBe("__global__");
  });

  it("delete_all with scope=global scopes the delete to the sentinel, not the user's whole memory set", async () => {
    // The more severe half of the same bug: delete_all reuses resolveAddParams
    // as its filter, and deleteAll() hits DELETE /v1/memories/ with raw query
    // params — no implicit null-scoping. Untagged, the filter degrades to
    // { userId } alone, which wipes every memory the user has in every project
    // and session, not just the global-scoped ones.
    mockMem0.deleteAll.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete_all", scope: "global" });
    expect(mockMem0.deleteAll).toHaveBeenCalledWith({ userId: "testuser", appId: "__global__" });
  });

  it("delete_all with scope=project stays scoped to the current project", async () => {
    mockMem0.deleteAll.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete_all", scope: "project" });
    expect(mockMem0.deleteAll).toHaveBeenCalledWith({ userId: "testuser", appId: "testproject" });
  });

  it("delete calls mem0.delete with full memory_id", async () => {
    mockMem0.delete.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete", memory_id: "abc12345-6789-0abc-def0-123456789abc" });
    expect(mockMem0.delete).toHaveBeenCalledWith("abc12345-6789-0abc-def0-123456789abc");
  });

  it("delete passes memory_id directly to mem0.delete", async () => {
    const fullId = "956e3d68-b420-4e07-a4e3-3019e7cebe6f";
    mockMem0.delete.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete", memory_id: fullId });
    expect(mockMem0.delete).toHaveBeenCalledWith(fullId);
  });
});