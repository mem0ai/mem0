import { describe, it, expect, vi, beforeEach } from "vitest";
import { detectRunId, resolveSearchFilters, resolveAddParams } from "./scoping.ts";

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

  it("only includes userId for global scope", () => {
    expect(resolveAddParams("global", ctx)).toEqual({ userId: "u1" });
  });
});
