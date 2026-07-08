import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { resolveUserId, buildRecallContext } from "./entry.ts";

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
