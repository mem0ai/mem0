/**
 * Unit tests for buildOSSMemoryConfig
 *
 * Covers the bug where setting `oss.historyDbPath` in the plugin config had no
 * effect at runtime. mem0ai's DEFAULT_MEMORY_CONFIG always initialises
 * `historyStore.config.historyDbPath` to "memory.db" (a relative path), and
 * the Memory constructor always prefers `historyStore` over the top-level
 * `historyDbPath` field. Without explicitly overriding `historyStore`, the
 * user-configured path was silently ignored, causing SQLITE_CANTOPEN crash
 * loops when the gateway ran as a macOS LaunchAgent (process.cwd() = "/").
 */

import { describe, it, expect } from "vitest";
import { buildOSSMemoryConfig } from "../index.js";

describe("buildOSSMemoryConfig", () => {
  describe("base config", () => {
    it("returns version v1.1 with no ossConfig", () => {
      const config = buildOSSMemoryConfig(undefined);
      expect(config).toEqual({ version: "v1.1" });
    });

    it("returns version v1.1 with empty ossConfig", () => {
      const config = buildOSSMemoryConfig({});
      expect(config).toEqual({ version: "v1.1" });
    });
  });

  describe("provider passthrough", () => {
    it("passes through embedder config", () => {
      const embedder = { provider: "ollama", config: { model: "bge-m3:latest", baseURL: "http://localhost:11434" } };
      const config = buildOSSMemoryConfig({ embedder });
      expect(config.embedder).toEqual(embedder);
    });

    it("passes through vectorStore config", () => {
      const vectorStore = { provider: "qdrant", config: { host: "localhost", port: 6333, collection: "memories" } };
      const config = buildOSSMemoryConfig({ vectorStore });
      expect(config.vectorStore).toEqual(vectorStore);
    });

    it("passes through llm config", () => {
      const llm = { provider: "ollama", config: { model: "llama3.2", baseURL: "http://localhost:11434" } };
      const config = buildOSSMemoryConfig({ llm });
      expect(config.llm).toEqual(llm);
    });

    it("passes through all providers together", () => {
      const ossConfig = {
        embedder: { provider: "openai", config: { model: "text-embedding-3-small" } },
        vectorStore: { provider: "qdrant", config: { host: "localhost", port: 6333 } },
        llm: { provider: "openai", config: { model: "gpt-4o-mini" } },
      };
      const config = buildOSSMemoryConfig(ossConfig);
      expect(config.embedder).toEqual(ossConfig.embedder);
      expect(config.vectorStore).toEqual(ossConfig.vectorStore);
      expect(config.llm).toEqual(ossConfig.llm);
    });
  });

  describe("historyDbPath handling", () => {
    it("does not set historyDbPath or historyStore when not configured", () => {
      const config = buildOSSMemoryConfig({});
      expect(config.historyDbPath).toBeUndefined();
      expect(config.historyStore).toBeUndefined();
    });

    it("sets historyDbPath when provided", () => {
      const path = "/Users/someone/.openclaw/memory/history.db";
      const config = buildOSSMemoryConfig({ historyDbPath: path });
      expect(config.historyDbPath).toBe(path);
    });

    it("sets historyStore with matching path when historyDbPath is provided", () => {
      const path = "/Users/someone/.openclaw/memory/history.db";
      const config = buildOSSMemoryConfig({ historyDbPath: path });
      expect(config.historyStore).toEqual({
        provider: "sqlite",
        config: { historyDbPath: path },
      });
    });

    it("historyStore.config.historyDbPath matches the configured historyDbPath", () => {
      // Regression: before the fix, mem0ai always took the historyStore branch
      // (merged from DEFAULT_MEMORY_CONFIG which sets historyDbPath = "memory.db").
      // This meant the user's explicit absolute path was never used.
      const explicitPath = "/absolute/path/to/history.db";
      const config = buildOSSMemoryConfig({ historyDbPath: explicitPath });
      const historyStore = config.historyStore as {
        provider: string;
        config: { historyDbPath: string };
      };
      expect(historyStore.config.historyDbPath).toBe(explicitPath);
      expect(historyStore.config.historyDbPath).not.toBe("memory.db");
    });

    it("applies resolvePath to historyDbPath before using it", () => {
      const relative = "memory/history.db";
      const resolved = "/home/user/.openclaw/memory/history.db";
      const resolvePath = (p: string) =>
        p.replace("memory/", "/home/user/.openclaw/memory/");

      const config = buildOSSMemoryConfig({ historyDbPath: relative }, resolvePath);

      expect(config.historyDbPath).toBe(resolved);
    });

    it("applies resolvePath to historyStore path as well", () => {
      const relative = "memory/history.db";
      const resolved = "/home/user/.openclaw/memory/history.db";
      const resolvePath = (p: string) =>
        p.replace("memory/", "/home/user/.openclaw/memory/");

      const config = buildOSSMemoryConfig({ historyDbPath: relative }, resolvePath);

      const historyStore = config.historyStore as {
        provider: string;
        config: { historyDbPath: string };
      };
      expect(historyStore.config.historyDbPath).toBe(resolved);
    });

    it("uses raw path when no resolvePath is provided", () => {
      const path = "/already/absolute/history.db";
      const config = buildOSSMemoryConfig({ historyDbPath: path });
      expect(config.historyDbPath).toBe(path);
      const historyStore = config.historyStore as {
        config: { historyDbPath: string };
      };
      expect(historyStore.config.historyDbPath).toBe(path);
    });
  });
});
