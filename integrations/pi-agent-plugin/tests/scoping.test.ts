import { describe, it, expect } from "vitest";
import { resolveAddParams, resolveSearchFilters, GLOBAL_APP_ID } from "../src/memory/scoping.ts";
import type { ScopeContext } from "../src/types.ts";

const ctx: ScopeContext = {
  userId: "kartik",
  appId: "my-project",
  runId: "session-abc123",
};

describe("resolveSearchFilters", () => {
  it("project scope returns user_id + app_id", () => {
    expect(resolveSearchFilters("project", ctx)).toEqual({
      user_id: "kartik", app_id: "my-project",
    });
  });

  it("session scope returns user_id + app_id + run_id", () => {
    expect(resolveSearchFilters("session", ctx)).toEqual({
      user_id: "kartik", app_id: "my-project", run_id: "session-abc123",
    });
  });

  it("global scope returns user_id with app_id wildcard", () => {
    expect(resolveSearchFilters("global", ctx)).toEqual({
      user_id: "kartik", app_id: "*",
    });
  });
});

describe("resolveAddParams", () => {
  it("project scope returns userId + appId (camelCase)", () => {
    expect(resolveAddParams("project", ctx)).toEqual({
      userId: "kartik", appId: "my-project",
    });
  });

  it("session scope includes runId", () => {
    expect(resolveAddParams("session", ctx)).toEqual({
      userId: "kartik", appId: "my-project", runId: "session-abc123",
    });
  });

  it("global scope tags appId with the reserved sentinel", () => {
    // Literal, not the imported GLOBAL_APP_ID — see src/memory/scoping.test.ts
    // for why asserting against the constant would pass on the unfixed code.
    expect(resolveAddParams("global", ctx)).toEqual({ userId: "kartik", appId: "__global__" });
  });

  it("exports the sentinel the global add path tags with", () => {
    expect(GLOBAL_APP_ID).toBe("__global__");
  });
});