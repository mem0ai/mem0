/**
 * Tests for config.ts — mem0ConfigSchema.parse() and exported constants.
 */
import { describe, it, expect } from "vitest";
import {
  mem0ConfigSchema,
  DEFAULT_CUSTOM_INSTRUCTIONS,
  DEFAULT_CUSTOM_CATEGORIES,
} from "../config.ts";

// ---------------------------------------------------------------------------
// Exported constants
// ---------------------------------------------------------------------------
describe("DEFAULT_CUSTOM_INSTRUCTIONS", () => {
  it("is a non-empty string", () => {
    expect(typeof DEFAULT_CUSTOM_INSTRUCTIONS).toBe("string");
    expect(DEFAULT_CUSTOM_INSTRUCTIONS.length).toBeGreaterThan(0);
  });
});

describe("DEFAULT_CUSTOM_CATEGORIES", () => {
  it("is a non-empty object with string values", () => {
    expect(typeof DEFAULT_CUSTOM_CATEGORIES).toBe("object");
    const keys = Object.keys(DEFAULT_CUSTOM_CATEGORIES);
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      expect(typeof DEFAULT_CUSTOM_CATEGORIES[key]).toBe("string");
    }
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — defaults
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — defaults", () => {
  it("mode defaults to 'platform' when omitted", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.mode).toBe("platform");
  });

  it("userId falls back to a non-empty string when not provided", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(typeof cfg.userId).toBe("string");
    expect(cfg.userId.length).toBeGreaterThan(0);
  });

  it("autoCapture defaults to true", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.autoCapture).toBe(true);
  });

  it("autoRecall defaults to true", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.autoRecall).toBe(true);
  });

  it("topK defaults to 5", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.topK).toBe(5);
  });

  it("searchThreshold defaults to 0.1", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.searchThreshold).toBe(0.1);
  });

  it("customInstructions defaults to DEFAULT_CUSTOM_INSTRUCTIONS", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.customInstructions).toBe(DEFAULT_CUSTOM_INSTRUCTIONS);
  });

  it("customCategories defaults to DEFAULT_CUSTOM_CATEGORIES", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.customCategories).toBe(DEFAULT_CUSTOM_CATEGORIES);
  });

  // v3.0.0: customPrompt removed, use customInstructions instead
  it("customPrompt input falls back to customInstructions", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key", customPrompt: "My prompt" });
    expect(cfg.customInstructions).toBe("My prompt");
  });

  it("oss defaults to undefined", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.oss).toBeUndefined();
  });

  it("skills defaults to undefined", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key" });
    expect(cfg.skills).toBeUndefined();
  });

  it("allows anonymousTelemetryId", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key", anonymousTelemetryId: "123" });
    expect(cfg.anonymousTelemetryId).toBe("123");
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — mode parsing
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — mode parsing", () => {
  it('"oss" is not a valid mode and defaults to "platform"', () => {
    const cfg = mem0ConfigSchema.parse({ mode: "oss", apiKey: "k" });
    expect(cfg.mode).toBe("platform");
  });

  it('"open-source" stays as "open-source"', () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source" });
    expect(cfg.mode).toBe("open-source");
  });

  it("any other string defaults to 'platform'", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "something-else", apiKey: "k" });
    expect(cfg.mode).toBe("platform");
  });

  it("undefined mode defaults to 'platform'", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k" });
    expect(cfg.mode).toBe("platform");
  });

  it("numeric mode defaults to 'platform'", () => {
    const cfg = mem0ConfigSchema.parse({ mode: 42, apiKey: "k" });
    expect(cfg.mode).toBe("platform");
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — userId precedence
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — userId", () => {
  it("userId from config takes precedence over os.userInfo() fallback", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "test-key",
      userId: "custom-user",
    });
    expect(cfg.userId).toBe("custom-user");
  });

  it("empty string userId falls back to os.userInfo()", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key", userId: "" });
    // Empty string is falsy, so the fallback should kick in
    expect(typeof cfg.userId).toBe("string");
    expect(cfg.userId.length).toBeGreaterThan(0);
  });

  it("non-string userId falls back to os.userInfo()", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key", userId: 123 });
    expect(typeof cfg.userId).toBe("string");
    expect(cfg.userId.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — needsSetup
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — needsSetup", () => {
  // Note: needsSetup = (mode === "platform" && !resolvedApiKey).
  // resolvedApiKey can come from the config OR from ~/.mem0/config.json fallback.
  // When no apiKey is provided and no config file exists, needsSetup is true.
  // When ~/.mem0/config.json has a key, the fallback populates resolvedApiKey.

  it("needsSetup is consistent: false when apiKey resolves, true otherwise (no apiKey in config)", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "platform" });
    // needsSetup should be true only if NO apiKey was resolved (including from ~/.mem0/config.json)
    if (cfg.apiKey) {
      expect(cfg.needsSetup).toBe(false);
    } else {
      expect(cfg.needsSetup).toBe(true);
    }
  });

  it("needsSetup is consistent with empty config", () => {
    const cfg = mem0ConfigSchema.parse({});
    if (cfg.apiKey) {
      expect(cfg.needsSetup).toBe(false);
    } else {
      expect(cfg.needsSetup).toBe(true);
    }
  });

  it("is false when apiKey is explicitly provided", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "my-api-key" });
    expect(cfg.needsSetup).toBe(false);
  });

  it("is false when mode is 'open-source' via explicit string (no apiKey needed)", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source" });
    expect(cfg.needsSetup).toBe(false);
  });

  it("is false when mode is 'open-source' (no apiKey needed)", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source" });
    expect(cfg.needsSetup).toBe(false);
  });

  it("needsSetup is always false when apiKey is a valid string", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "test-key-123" });
    expect(cfg.apiKey).toBe("test-key-123");
    expect(cfg.needsSetup).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — error cases
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — error cases", () => {
  it("throws on unknown keys", () => {
    expect(() =>
      mem0ConfigSchema.parse({ apiKey: "k", unknownKey: "value" }),
    ).toThrow(/unknown keys.*unknownKey/);
  });

  it("throws when multiple unknown keys are present", () => {
    expect(() =>
      mem0ConfigSchema.parse({ apiKey: "k", foo: 1, bar: 2 }),
    ).toThrow(/unknown keys/);
  });

  it("throws on null input", () => {
    expect(() => mem0ConfigSchema.parse(null)).toThrow(
      "openclaw-mem0 config required",
    );
  });

  it("throws on undefined input", () => {
    expect(() => mem0ConfigSchema.parse(undefined)).toThrow(
      "openclaw-mem0 config required",
    );
  });

  it("throws on string input", () => {
    expect(() => mem0ConfigSchema.parse("not an object")).toThrow(
      "openclaw-mem0 config required",
    );
  });

  it("throws on number input", () => {
    expect(() => mem0ConfigSchema.parse(42)).toThrow(
      "openclaw-mem0 config required",
    );
  });

  it("throws on array input", () => {
    expect(() => mem0ConfigSchema.parse([1, 2, 3])).toThrow(
      "openclaw-mem0 config required",
    );
  });

  it("throws on boolean input", () => {
    expect(() => mem0ConfigSchema.parse(true)).toThrow(
      "openclaw-mem0 config required",
    );
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — explicit overrides
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — explicit overrides", () => {
  it("autoCapture can be set to false", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      autoCapture: false,
    });
    expect(cfg.autoCapture).toBe(false);
  });

  it("autoRecall can be set to false", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      autoRecall: false,
    });
    expect(cfg.autoRecall).toBe(false);
  });

  it("custom topK is used when provided", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k", topK: 20 });
    expect(cfg.topK).toBe(20);
  });

  it("custom searchThreshold is used when provided", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      searchThreshold: 0.8,
    });
    expect(cfg.searchThreshold).toBe(0.8);
  });

  it("custom customInstructions override defaults", () => {
    const custom = "My custom instructions";
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customInstructions: custom,
    });
    expect(cfg.customInstructions).toBe(custom);
  });

  // v3.0.0: customPrompt renamed to customInstructions (backwards compat: customPrompt maps to customInstructions)
  it("customPrompt input maps to customInstructions output", () => {
    const custom = "My custom prompt";
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customPrompt: custom,
    });
    expect(cfg.customInstructions).toBe(custom);
  });

  it("custom customCategories override defaults", () => {
    const cats = { myCategory: "description" };
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customCategories: cats,
    });
    expect(cfg.customCategories).toEqual(cats);
  });

  it("baseUrl is passed through when provided", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      baseUrl: "https://custom.api.com",
    });
    expect(cfg.baseUrl).toBe("https://custom.api.com");
  });

});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — oss config
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — oss config", () => {
  it("parses oss object when provided", () => {
    const ossConfig = {
      embedder: {
        provider: "openai",
        config: { model: "text-embedding-3-small" },
      },
      vectorStore: { provider: "qdrant", config: { host: "localhost" } },
      llm: { provider: "openai", config: { model: "gpt-4" } },
      historyDbPath: "/tmp/history.db",
      disableHistory: false,
    };
    const cfg = mem0ConfigSchema.parse({ mode: "open-source", oss: ossConfig });
    expect(cfg.mode).toBe("open-source");
    expect(cfg.oss).toEqual(ossConfig);
  });

  it("ignores oss when it is not a plain object", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source", oss: "not-an-object" });
    expect(cfg.oss).toBeUndefined();
  });

  it("ignores oss when it is an array", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source", oss: [1, 2, 3] });
    expect(cfg.oss).toBeUndefined();
  });

  it("ignores oss when it is null", () => {
    const cfg = mem0ConfigSchema.parse({ mode: "open-source", oss: null });
    expect(cfg.oss).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — skills config
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — skills config", () => {
  it("parses skills object when provided", () => {
    const skillsConfig = {
      triage: {
        enabled: true,
        importanceThreshold: 3,
        credentialPatterns: ["sk-", "ghp_"],
      },
      recall: {
        enabled: true,
        strategy: "smart" as const,
        tokenBudget: 2000,
        maxMemories: 10,
      },
      dream: {
        enabled: true,
        auto: true,
        minHours: 12,
        minSessions: 3,
        minMemories: 15,
      },
      domain: "engineering",
      customRules: {
        include: ["tool configs"],
        exclude: ["passwords"],
      },
      categories: {
        identity: {
          importance: 5,
          ttl: null,
          immutable: true,
        },
      },
    };
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      skills: skillsConfig,
    });
    expect(cfg.skills).toEqual(skillsConfig);
  });

  it("skills is undefined when not provided", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k" });
    expect(cfg.skills).toBeUndefined();
  });

  it("skills is undefined when set to a non-object value", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k", skills: "invalid" });
    expect(cfg.skills).toBeUndefined();
  });

  it("skills is undefined when set to an array", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k", skills: [1, 2] });
    expect(cfg.skills).toBeUndefined();
  });

  it("skills is undefined when set to null", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "k", skills: null });
    expect(cfg.skills).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — customCategories edge cases
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — customCategories edge cases", () => {
  it("non-object customCategories falls back to defaults", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customCategories: "not-an-object",
    });
    expect(cfg.customCategories).toBe(DEFAULT_CUSTOM_CATEGORIES);
  });

  it("array customCategories falls back to defaults", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customCategories: ["a", "b"],
    });
    expect(cfg.customCategories).toBe(DEFAULT_CUSTOM_CATEGORIES);
  });

  it("null customCategories falls back to defaults", () => {
    const cfg = mem0ConfigSchema.parse({
      apiKey: "k",
      customCategories: null,
    });
    expect(cfg.customCategories).toBe(DEFAULT_CUSTOM_CATEGORIES);
  });
});

// ---------------------------------------------------------------------------
// mem0ConfigSchema.parse() — non-string apiKey
// ---------------------------------------------------------------------------
describe("mem0ConfigSchema.parse() — apiKey edge cases", () => {
  // Note: When a non-string apiKey is provided, the parser treats it as
  // undefined. However, readMem0ConfigFile() may still provide a fallback
  // apiKey from ~/.mem0/config.json if one exists on the system.

  it("non-string apiKey is not used directly from config", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: 12345 });
    // The numeric value is not used directly — apiKey comes from fallback or is undefined
    // Either way, the non-string value is never the resolved apiKey
    expect(cfg.apiKey).not.toBe(12345);
  });

  it("boolean apiKey is not used directly from config", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: true });
    expect(cfg.apiKey).not.toBe(true);
  });

  it("string apiKey takes precedence over any fallback", () => {
    const cfg = mem0ConfigSchema.parse({ apiKey: "explicit-key" });
    expect(cfg.apiKey).toBe("explicit-key");
    expect(cfg.needsSetup).toBe(false);
  });
});
