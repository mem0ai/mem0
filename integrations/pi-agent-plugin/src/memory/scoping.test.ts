import { describe, it, expect, vi, beforeEach } from "vitest";
import { detectRunId, resolveSearchFilters, resolveAddParams, GLOBAL_APP_ID } from "./scoping.ts";

const mockExecFileSync = vi.fn();

vi.mock("node:child_process", () => ({
  execFileSync: (...args: any[]) => mockExecFileSync(...args),
}));

const { detectAppId } = await import("./scoping.ts");

describe("detectAppId", () => {
  beforeEach(() => {
    mockExecFileSync.mockReset();
  });

  it("uses git root basename for a git repo", () => {
    mockExecFileSync.mockReturnValue("/home/user/projects/my-app\n");
    expect(detectAppId("/home/user/projects/my-app")).toBe("my-app");
  });

  it("returns same app_id from any subdirectory in a monorepo", () => {
    mockExecFileSync.mockReturnValue("/home/user/projects/monorepo\n");
    const root = detectAppId("/home/user/projects/monorepo");
    const sub = detectAppId("/home/user/projects/monorepo/packages/core");
    expect(root).toBe("monorepo");
    expect(sub).toBe("monorepo");
  });

  it("falls back to basename when not in a git repo", () => {
    mockExecFileSync.mockImplementation(() => {
      throw new Error("fatal: not a git repository");
    });
    expect(detectAppId("/home/user/scratch")).toBe("scratch");
  });
});

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

  it("uses wildcard app_id for global scope", () => {
    expect(resolveSearchFilters("global", ctx)).toEqual({ user_id: "u1", app_id: "*" });
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

  it("tags global scope with the reserved GLOBAL_APP_ID instead of leaving appId unset", () => {
    // Regression test: resolveSearchFilters("global", ...) filters on app_id: "*",
    // which only matches non-null values. Writing without an appId would persist
    // app_id: null and make the memory permanently unreachable by that search —
    // see resolveSearchFilters's "global" test above for the read-side half.
    expect(resolveAddParams("global", ctx)).toEqual({ userId: "u1", appId: GLOBAL_APP_ID });
  });
});

describe("resolveAddParams / resolveSearchFilters scoping fields stay in sync", () => {
  const ctx = { userId: "u1", appId: "a1", runId: "r1" };
  const scopingFields: Record<string, string> = { userId: "user_id", appId: "app_id", runId: "run_id" };

  for (const scope of ["project", "session", "global"] as const) {
    it(`add sets every scoping field that search filters on for "${scope}" scope`, () => {
      // A memory added under a given scope must be findable by a search under that
      // same scope: search can't require a field (as a non-null match or wildcard)
      // that the write never sets to a non-null value.
      const addKeys = new Set(Object.keys(resolveAddParams(scope, ctx)));
      const searchKeys = new Set(
        Object.keys(resolveSearchFilters(scope, ctx)).map((k) => scopingFields[k] ?? k),
      );
      const addKeysNormalized = new Set([...addKeys].map((k) => scopingFields[k] ?? k));
      expect(addKeysNormalized).toEqual(searchKeys);
    });
  }
});
