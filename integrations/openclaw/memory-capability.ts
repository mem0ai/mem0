/**
 * Memory capability for OpenClaw's plugin runtime seam.
 *
 * This plugin exposes memory through tools (memory_search, memory_add, ...)
 * and lifecycle hooks. It does not implement OpenClaw's programmatic
 * MemorySearchManager contract (search/readFile/status/probe*), so
 * getMemorySearchManager reports `manager: null` with an explanation.
 * Returning a partial manager instead crashes consumers that trust the
 * contract: memory-wiki shared search and realtime-voice fast context call
 * manager.search(), and status scans call manager.probeVectorAvailability().
 *
 * No publicArtifacts provider is registered either: OpenClaw public
 * artifacts describe files on disk (workspaceDir, relativePath,
 * absolutePath, kind, contentType), while mem0 memories are database
 * records with no backing file. Exporting record-shaped artifacts crashes
 * the gateway's artifact sort with `undefined.localeCompare`.
 */

import type { Mem0Config } from "./types.ts";
import { DEFAULT_BASE_URL } from "./cli/config-file.ts";

export const SEARCH_MANAGER_UNAVAILABLE =
  "openclaw-mem0 does not implement the programmatic MemorySearchManager " +
  'contract; use the memory_* tools, or set memory-wiki search.backend="local" ' +
  "for wiki-only search";

/** Build the payload for api.registerMemoryCapability(). */
export function createMemoryCapability(cfg: Mem0Config) {
  return {
    runtime: {
      async getMemorySearchManager() {
        return { manager: null, error: SEARCH_MANAGER_UNAVAILABLE };
      },
      resolveMemoryBackendConfig() {
        return {
          backend: cfg.mode,
          baseUrl: cfg.baseUrl ?? DEFAULT_BASE_URL,
          userId: cfg.userId,
        };
      },
      async closeAllMemorySearchManagers() {},
    },
  };
}
