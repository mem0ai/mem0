/**
 * Tests for configuration management.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  createDefaultConfig,
  loadConfig,
  saveConfig,
  redactKey,
  getNestedValue,
  setNestedValue,
  CONFIG_DIR,
  CONFIG_FILE,
} from "../src/config.js";

// Use a temp directory for config during tests
let origConfigDir: string;
let origConfigFile: string;
let tmpDir: string;

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-test-"));
  // Monkey-patch the module-level constants
  // We'll use env vars and direct file manipulation instead
  // Clear MEM0_ env vars
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("MEM0_")) {
      delete process.env[key];
    }
  }
});

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

describe("redactKey", () => {
  it("returns '(not set)' for empty key", () => {
    expect(redactKey("")).toBe("(not set)");
  });

  it("redacts short key", () => {
    expect(redactKey("abc")).toBe("ab***");
  });

  it("redacts normal key", () => {
    const result = redactKey("m0-abcdefgh12345678");
    expect(result).toBe("m0-a...5678");
    expect(result).not.toContain("abcdefgh");
  });

  it("redacts exactly 8-char key as short", () => {
    expect(redactKey("12345678")).toBe("12***");
  });
});

describe("createDefaultConfig", () => {
  it("has correct defaults", () => {
    const config = createDefaultConfig();
    expect(config.platform.baseUrl).toBe("https://api.mem0.ai");
    expect(config.platform.apiKey).toBe("");
    expect(config.defaults.userId).toBe("");
  });
});

describe("getNestedValue", () => {
  it("gets platform.api_key", () => {
    const config = createDefaultConfig();
    config.platform.apiKey = "test-key";
    expect(getNestedValue(config, "platform.api_key")).toBe("test-key");
  });

  it("returns undefined for nonexistent key", () => {
    const config = createDefaultConfig();
    expect(getNestedValue(config, "nonexistent.key")).toBeUndefined();
  });

  it("gets defaults.user_id", () => {
    const config = createDefaultConfig();
    config.defaults.userId = "alice";
    expect(getNestedValue(config, "defaults.user_id")).toBe("alice");
  });
});

describe("setNestedValue", () => {
  it("sets platform.api_key", () => {
    const config = createDefaultConfig();
    expect(setNestedValue(config, "platform.api_key", "new-key")).toBe(true);
    expect(config.platform.apiKey).toBe("new-key");
  });

  it("returns false for nonexistent key", () => {
    const config = createDefaultConfig();
    expect(setNestedValue(config, "nonexistent.key", "val")).toBe(false);
  });

  it("sets defaults.user_id", () => {
    const config = createDefaultConfig();
    expect(setNestedValue(config, "defaults.user_id", "bob")).toBe(true);
    expect(config.defaults.userId).toBe("bob");
  });

});
