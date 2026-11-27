import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { detectRunId, resolveSearchFilters, resolveAddParams } from "./scoping.ts";

const mockExecFileSync = vi.fn();

vi.mock("node:child_process", () => ({
  execFileSync: (...args: any[]) => mockExecFileSync(...args),
}));

const { detectAppId } = await import("./scoping.ts");

describe("detectAppId", () => {
  const originalEnvAppId = process.env.MEM0_APP_ID;

  beforeEach(() => {
    mockExecFileSync.mockReset();
    delete process.env.MEM0_APP_ID;
  });

  afterEach(() => {
    if (originalEnvAppId === undefined) {
      delete process.env.MEM0_APP_ID;
    } else {
      process.env.MEM0_APP_ID = originalEnvAppId;
    }
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

  it("prefers MEM0_APP_ID over the git root", () => {
    process.env.MEM0_APP_ID = "pinned-app";
    mockExecFileSync.mockReturnValue("/home/user/projects/my-app\n");
    expect(detectAppId("/home/user/projects/my-app")).toBe("pinned-app");
    expect(mockExecFileSync).not.toHaveBeenCalled();
  });

  it("uses MEM0_APP_ID outside a git repository", () => {
    process.env.MEM0_APP_ID = "pinned-app";
    mockExecFileSync.mockImplementation(() => {
      throw new Error("fatal: not a git repository");
    });
    expect(detectAppId("/home/user/scratch")).toBe("pinned-app");
  });

  it("falls through to git detection for an empty MEM0_APP_ID", () => {
    process.env.MEM0_APP_ID = "";
    mockExecFileSync.mockReturnValue("/home/user/projects/my-app\n");
    expect(detectAppId("/home/user/projects/my-app")).toBe("my-app");
  });

  it("falls through to git detection for a whitespace-only MEM0_APP_ID", () => {
    mockExecFileSync.mockReturnValue("/home/user/projects/my-app\n");
    for (const value of ["  ", "\t", "\n  "]) {
      process.env.MEM0_APP_ID = value;
      expect(detectAppId("/home/user/projects/my-app")).toBe("my-app");
    }
  });

  it("falls through to git detection for a wildcard MEM0_APP_ID", () => {
    process.env.MEM0_APP_ID = "*";
    mockExecFileSync.mockReturnValue("/home/user/projects/my-app\n");
    expect(detectAppId("/home/user/projects/my-app")).toBe("my-app");
  });

  it("uses a padded MEM0_APP_ID verbatim", () => {
    process.env.MEM0_APP_ID = "  my-app  ";
    mockExecFileSync.mockReturnValue("/home/user/projects/other-repo\n");
    expect(detectAppId("/home/user/projects/other-repo")).toBe("  my-app  ");
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
