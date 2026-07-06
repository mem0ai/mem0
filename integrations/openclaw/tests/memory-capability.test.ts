/**
 * Tests for memory-capability.ts — the payload handed to
 * api.registerMemoryCapability().
 *
 * Regression guards for two OpenClaw-side crashes caused by the previous
 * registration:
 * - a partial search manager (no `search`) broke memory-wiki shared search
 *   and realtime-voice fast context with
 *   "sharedMemoryManager.search is not a function"
 * - record-shaped public artifacts (no workspaceDir/relativePath/kind/
 *   contentType/absolutePath) crashed the gateway artifact sort with
 *   "Cannot read properties of undefined (reading 'localeCompare')"
 */
import { describe, it, expect } from "vitest";

import {
  createMemoryCapability,
  SEARCH_MANAGER_UNAVAILABLE,
} from "../memory-capability.ts";
import { DEFAULT_BASE_URL } from "../cli/config-file.ts";
import type { Mem0Config } from "../types.ts";

function makeConfig(overrides: Partial<Mem0Config> = {}): Mem0Config {
  return {
    mode: "open-source",
    customInstructions: "",
    customCategories: {},
    userId: "user-1",
    autoCapture: false,
    autoRecall: false,
    searchThreshold: 0.1,
    topK: 5,
    ...overrides,
  };
}

describe("createMemoryCapability", () => {
  it("registers no publicArtifacts provider", () => {
    // OpenClaw public artifacts are files on disk; mem0 memories have no
    // backing file, so there is nothing valid to export.
    expect("publicArtifacts" in createMemoryCapability(makeConfig())).toBe(false);
  });

  describe("runtime.getMemorySearchManager", () => {
    it("reports the manager as unavailable instead of returning a partial manager", async () => {
      const { runtime } = createMemoryCapability(makeConfig());
      await expect(runtime.getMemorySearchManager()).resolves.toEqual({
        manager: null,
        error: SEARCH_MANAGER_UNAVAILABLE,
      });
    });

    it("points at the wiki-only search fallback in the error", () => {
      expect(SEARCH_MANAGER_UNAVAILABLE).toContain('search.backend="local"');
    });
  });

  describe("runtime.resolveMemoryBackendConfig", () => {
    it("returns the configured backend, baseUrl, and userId", () => {
      const { runtime } = createMemoryCapability(
        makeConfig({
          mode: "platform",
          baseUrl: "https://mem0.example.com",
          userId: "u-42",
        }),
      );
      expect(runtime.resolveMemoryBackendConfig()).toEqual({
        backend: "platform",
        baseUrl: "https://mem0.example.com",
        userId: "u-42",
      });
    });

    it("falls back to the default platform baseUrl", () => {
      const { runtime } = createMemoryCapability(makeConfig());
      expect(runtime.resolveMemoryBackendConfig().baseUrl).toBe(DEFAULT_BASE_URL);
    });
  });

  it("closeAllMemorySearchManagers resolves", async () => {
    const { runtime } = createMemoryCapability(makeConfig());
    await expect(runtime.closeAllMemorySearchManagers()).resolves.toBeUndefined();
  });
});
