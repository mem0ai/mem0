import { describe, it, expect } from "vitest";
import { resolveAddParams, resolveSearchFilters } from "../src/memory/scoping.ts";
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

  it("global scope returns userId only", () => {
    expect(resolveAddParams("global", ctx)).toEqual({ userId: "kartik" });
  });
});
