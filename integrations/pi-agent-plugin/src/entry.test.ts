import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import mem0Extension, { resolveUserId, buildRecallContext } from "./entry.ts";
import { resolveRepoContext } from "../../agent-plugin-core/typescript/src/identity.ts";

const search = vi.fn().mockResolvedValue({ results: [{ id: "m1", memory: "Tests run with vitest" }] });

vi.mock("mem0ai", () => ({
  default: class {
    headers = {};
    search = search;
    add = vi.fn();
  },
}));
vi.mock("./telemetry.ts", () => ({ captureEvent: vi.fn() }));

describe("resolveUserId", () => {
  const originalEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("returns config userId when set", () => {
    expect(resolveUserId("config-user")).toBe("config-user");
  });

  it("falls back to USER env var", () => {
    process.env.USER = "env-user";
    delete process.env.USERNAME;
    expect(resolveUserId("")).toBe("env-user");
  });

  it("falls back to USERNAME env var on Windows", () => {
    delete process.env.USER;
    process.env.USERNAME = "win-user";
    expect(resolveUserId("")).toBe("win-user");
  });

  it("falls back to os.userInfo() when env vars are missing", () => {
    delete process.env.USER;
    delete process.env.USERNAME;
    const result = resolveUserId("");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("buildRecallContext", () => {
  const search = async () => ({
    results: [{ id: "m1", memory: "User prefers pnpm over npm", categories: ["preferences"] }],
  });

  it("returns empty when disabled", async () => {
    expect(await buildRecallContext("which pm?", false, search)).toBe("");
  });

  it("returns empty for a blank prompt", async () => {
    expect(await buildRecallContext("   ", true, search)).toBe("");
  });

  it("returns empty when no memories match", async () => {
    expect(await buildRecallContext("hi", true, async () => ({ results: [] }))).toBe("");
  });

  it("injects recalled memory text when enabled and matches exist", async () => {
    const out = await buildRecallContext("which pm?", true, search);
    expect(out).toContain("User prefers pnpm over npm");
    expect(out).toContain("mem0-relevant-memories");
  });

  it("swallows search errors so the turn is never blocked", async () => {
    const out = await buildRecallContext("hi", true, async () => {
      throw new Error("boom");
    });
    expect(out).toBe("");
  });
});

describe("automatic recall", () => {
  const originalEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("searches the repository lanes once, on the first prompt", async () => {
    process.env.MEM0_API_KEY = "m0-test";
    const handlers: Record<string, (event: any, ctx: any) => Promise<any>> = {};
    mem0Extension({ on: (name: string, handler: any) => { handlers[name] = handler; }, registerTool: vi.fn(), registerCommand: vi.fn() } as any);
    const ctx = { cwd: process.cwd(), sessionManager: { getSessionFile: () => "/tmp/session.json" } };
    await handlers.session_start({ reason: "startup" }, ctx);

    const first = await handlers.before_agent_start({ prompt: "How do I run the tests here?", systemPrompt: "base" }, ctx);
    const second = await handlers.before_agent_start({ prompt: "And how do I build the plugin?", systemPrompt: "base" }, ctx);

    expect(search).toHaveBeenCalledTimes(1);
    const [, options] = search.mock.calls[0];
    expect(options).toMatchObject({ topK: 5, rerank: false, latestOnly: true });
    const repo = resolveRepoContext(process.cwd());
    expect(JSON.stringify(options.filters.OR[0])).toContain(`{"agent_id":"${repo.projectId}"}`);
    expect(options.filters.OR[1]).toEqual({ AND: [{ user_id: expect.any(String) }, { app_id: repo.appId }] });
    expect(first.systemPrompt).toContain("1. Tests run with vitest");
    expect(second.systemPrompt).toBe(first.systemPrompt);
  });
});
