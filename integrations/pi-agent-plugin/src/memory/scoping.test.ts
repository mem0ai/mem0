import { describe, it, expect } from "vitest";
import { detectRunId, resolveSearchFilters, resolveAddParams } from "./scoping.ts";

describe("detectRunId", () => {
  it("returns 'unknown' when no session file", () => {
    expect(detectRunId(undefined)).toBe("unknown");
  });

  it("returns a 12-char hex hash for a session file", () => {
    const id = detectRunId("/tmp/session-abc.json");
    expect(id).toMatch(/^[0-9a-f]{12}$/);
  });

  it("produces different IDs for different session files", () => {
    const a = detectRunId("/tmp/session-a.json");
    const b = detectRunId("/tmp/session-b.json");
    expect(a).not.toBe(b);
  });
});

describe("resolveSearchFilters", () => {
  const ctx = { userId: "u1", appId: "a1", runId: "r1" };

  it("includes user_id and app_id for project scope", () => {
    expect(resolveSearchFilters("project", ctx)).toEqual({ user_id: "u1", app_id: "a1" });
  });

  it("includes run_id for session scope", () => {
    expect(resolveSearchFilters("session", ctx)).toEqual({ user_id: "u1", app_id: "a1", run_id: "r1" });
  });

  it("limits global scope to the configured user", () => {
    expect(resolveSearchFilters("global", ctx)).toEqual({ user_id: "u1" });
  });
});

describe("resolveAddParams", () => {
  const ctx = { userId: "u1", appId: "a1", runId: "r1" };

  it("includes userId and appId for project scope", () => {
    expect(resolveAddParams("project", ctx)).toEqual({ userId: "u1", appId: "a1" });
  });

  it("includes runId for session scope", () => {
    expect(resolveAddParams("session", ctx)).toEqual({ userId: "u1", appId: "a1", runId: "r1" });
  });

  it("only includes userId for global scope", () => {
    expect(resolveAddParams("global", ctx)).toEqual({ userId: "u1" });
  });
});
