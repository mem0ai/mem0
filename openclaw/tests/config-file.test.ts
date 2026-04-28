/**
 * Tests for cli/config-file.ts — file-based config helpers.
 *
 * All filesystem operations are mocked via fs-safe.ts so tests never
 * touch the real disk.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../fs-safe.ts", () => ({
  readText: vi.fn(),
  exists: vi.fn(),
  writeText: vi.fn(),
  mkdirp: vi.fn(),
  unlink: vi.fn(),
}));

import { readText, exists, writeText, mkdirp } from "../fs-safe.ts";
import {
  readPluginAuth,
  writePluginAuth,
  getBaseUrl,
  DEFAULT_BASE_URL,
} from "../cli/config-file.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockExists = exists as ReturnType<typeof vi.fn>;
const mockReadText = readText as ReturnType<typeof vi.fn>;
const mockWriteText = writeText as ReturnType<typeof vi.fn>;
const mockMkdirp = mkdirp as ReturnType<typeof vi.fn>;

function setConfigFile(obj: Record<string, unknown>): void {
  mockExists.mockReturnValue(true);
  mockReadText.mockReturnValue(JSON.stringify(obj));
}

function setNoFile(): void {
  mockExists.mockReturnValue(false);
}

beforeEach(() => {
  vi.resetAllMocks();
});

// ---------------------------------------------------------------------------
// readPluginAuth
// ---------------------------------------------------------------------------

describe("readPluginAuth", () => {
  it("returns empty object when config file does not exist", () => {
    setNoFile();
    expect(readPluginAuth()).toEqual({});
  });

  it("returns empty object when config has no plugins section", () => {
    setConfigFile({ someOtherKey: true });
    expect(readPluginAuth()).toEqual({});
  });

  it("reads all fields correctly from nested config", () => {
    setConfigFile({
      plugins: {
        entries: {
          "openclaw-mem0": {
            enabled: true,
            config: {
              apiKey: "sk-test-123",
              baseUrl: "https://custom.api.com",
              userId: "user-1",
              mode: "platform",
              autoRecall: true,
              autoCapture: false,
              topK: 10,
            },
          },
        },
      },
    });

    const auth = readPluginAuth();
    expect(auth).toEqual({
      apiKey: "sk-test-123",
      baseUrl: "https://custom.api.com",
      userId: "user-1",
      mode: "platform",
      autoRecall: true,
      autoCapture: false,
      topK: 10,
    });
  });

  it("handles snake_case aliases (api_key, base_url, user_id)", () => {
    setConfigFile({
      plugins: {
        entries: {
          "openclaw-mem0": {
            enabled: true,
            config: {
              api_key: "sk-snake",
              base_url: "https://snake.api.com",
              user_id: "user-snake",
            },
          },
        },
      },
    });

    const auth = readPluginAuth();
    expect(auth.apiKey).toBe("sk-snake");
    expect(auth.baseUrl).toBe("https://snake.api.com");
    expect(auth.userId).toBe("user-snake");
  });

  it("throws error when JSON is invalid (prevents config destruction)", () => {
    mockExists.mockReturnValue(true);
    mockReadText.mockReturnValue("not valid json {{{");
    expect(() => readPluginAuth()).toThrow(/Failed to parse[\s\S]*Fix the JSON syntax error/);
  });

  it("returns empty object when config file is empty", () => {
    mockExists.mockReturnValue(true);
    mockReadText.mockReturnValue("   ");
    expect(readPluginAuth()).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// writePluginAuth
// ---------------------------------------------------------------------------

describe("writePluginAuth", () => {
  it("creates nested structure from scratch when no config exists", () => {
    setNoFile();
    // exists returns false for both the file (readFullConfig) and the dir (writeFullConfig)
    mockExists.mockReturnValue(false);

    writePluginAuth({ apiKey: "sk-new", userId: "u1" });

    expect(mockMkdirp).toHaveBeenCalled();
    expect(mockWriteText).toHaveBeenCalledOnce();

    const written = JSON.parse(mockWriteText.mock.calls[0][1]);
    expect(written.plugins.entries["openclaw-mem0"].enabled).toBe(true);
    expect(written.plugins.entries["openclaw-mem0"].config.apiKey).toBe(
      "sk-new",
    );
    expect(written.plugins.entries["openclaw-mem0"].config.userId).toBe("u1");
  });

  it("merges into existing config preserving other data", () => {
    setConfigFile({
      otherSetting: "keep-me",
      plugins: {
        entries: {
          "openclaw-mem0": {
            enabled: true,
            config: {
              apiKey: "sk-old",
              mode: "platform",
            },
          },
        },
      },
    });

    writePluginAuth({ baseUrl: "https://new.api.com" });

    const written = JSON.parse(mockWriteText.mock.calls[0][1]);
    // Existing fields preserved
    expect(written.otherSetting).toBe("keep-me");
    expect(written.plugins.entries["openclaw-mem0"].config.apiKey).toBe(
      "sk-old",
    );
    expect(written.plugins.entries["openclaw-mem0"].config.mode).toBe(
      "platform",
    );
    // New field added
    expect(written.plugins.entries["openclaw-mem0"].config.baseUrl).toBe(
      "https://new.api.com",
    );
  });

  it("creates directory if missing", () => {
    // File doesn't exist (readFullConfig returns {}), dir doesn't exist
    mockExists.mockReturnValue(false);

    writePluginAuth({ apiKey: "sk-test" });

    expect(mockMkdirp).toHaveBeenCalledWith(
      expect.stringContaining(".openclaw"),
      0o700,
    );
  });

  it("skips undefined values", () => {
    setNoFile();
    mockExists.mockReturnValue(false);

    writePluginAuth({
      apiKey: "sk-set",
      baseUrl: undefined,
      userId: undefined,
    });

    const written = JSON.parse(mockWriteText.mock.calls[0][1]);
    const cfg = written.plugins.entries["openclaw-mem0"].config;
    expect(cfg.apiKey).toBe("sk-set");
    expect(cfg).not.toHaveProperty("baseUrl");
    expect(cfg).not.toHaveProperty("userId");
  });
});

// ---------------------------------------------------------------------------
// getBaseUrl
// ---------------------------------------------------------------------------

describe("getBaseUrl", () => {
  it("returns configured URL when baseUrl is set", () => {
    setConfigFile({
      plugins: {
        entries: {
          "openclaw-mem0": {
            enabled: true,
            config: { baseUrl: "https://custom.example.com" },
          },
        },
      },
    });

    expect(getBaseUrl()).toBe("https://custom.example.com");
  });

  it("returns default URL when baseUrl is not configured", () => {
    setNoFile();
    expect(getBaseUrl()).toBe(DEFAULT_BASE_URL);
  });
});
