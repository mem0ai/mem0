import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { resolveUserId } from "./entry.ts";

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
