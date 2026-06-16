import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import { loadConfig } from "../src/config/index.ts";

vi.mock("node:fs");

describe("loadConfig", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv, HOME: "/home/testuser" };
    vi.mocked(fs.existsSync).mockReturnValue(false);
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.restoreAllMocks();
  });

  it("reads config from env vars when no config file exists", () => {
    process.env.MEM0_API_KEY = "m0-test-key";
    process.env.MEM0_USER_ID = "env-user";
    const config = loadConfig();
    expect(config.apiKey).toBe("m0-test-key");
    expect(config.userId).toBe("env-user");
    expect(config.autoCapture).toBe(true);
    expect(config.defaultScope).toBe("project");
  });

  it("returns empty apiKey when no key found anywhere", () => {
    delete process.env.MEM0_API_KEY;
    const config = loadConfig();
    expect(config.apiKey).toBe("");
  });

  it("reads config file and merges with defaults", () => {
    delete process.env.MEM0_API_KEY;
    delete process.env.MEM0_USER_ID;
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readFileSync).mockReturnValue(
      JSON.stringify({ apiKey: "m0-file-key", userId: "file-user" })
    );
    const config = loadConfig();
    expect(config.apiKey).toBe("m0-file-key");
    expect(config.userId).toBe("file-user");
    expect(config.dream.enabled).toBe(true);
    expect(config.dream.minHours).toBe(24);
  });

  it("env vars override config file", () => {
    process.env.MEM0_API_KEY = "m0-env-key";
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readFileSync).mockReturnValue(
      JSON.stringify({ apiKey: "m0-file-key" })
    );
    const config = loadConfig();
    expect(config.apiKey).toBe("m0-env-key");
  });
});
