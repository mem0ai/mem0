/**
 * Memory capability for OpenClaw's plugin runtime seam.
 *
 * Wraps the Mem0 provider's search/get into the MemorySearchManager
 * contract so memory-wiki shared search, realtime-voice fast context,
 * and status scans can consume mem0 memories programmatically.
 *
 * No publicArtifacts provider — mem0 memories are database records
 * with no backing file, not the file-on-disk shape the contract needs.
 */

import type { Mem0Config, Mem0Provider, MemoryItem } from "./types.ts";
import type {
  MemorySearchManager,
  MemorySearchResult,
  MemoryProviderStatus,
  MemoryEmbeddingProbeResult,
} from "openclaw/plugin-sdk";
import { DEFAULT_BASE_URL } from "./cli/config-file.ts";

const MEM0_PATH_PREFIX = "mem0://";

function memoryToSearchResult(item: MemoryItem): MemorySearchResult {
  return {
    path: `${MEM0_PATH_PREFIX}${item.id}`,
    startLine: 0,
    endLine: 0,
    score: item.score ?? 0,
    snippet: item.memory,
    source: "memory",
    citation: item.categories?.length ? item.categories.join(", ") : undefined,
  };
}

class Mem0SearchManager implements MemorySearchManager {
  constructor(
    private provider: Mem0Provider,
    private cfg: Mem0Config,
    private effectiveUserId: (sessionKey?: string) => string,
  ) {}

  async search(
    query: string,
    opts?: { maxResults?: number; minScore?: number; sessionKey?: string },
  ): Promise<MemorySearchResult[]> {
    const results = await this.provider.search(query, {
      user_id: this.effectiveUserId(opts?.sessionKey),
      top_k: opts?.maxResults ?? this.cfg.topK,
      threshold: opts?.minScore ?? this.cfg.searchThreshold,
      source: "OPENCLAW",
    });
    return results.map(memoryToSearchResult);
  }

  async readFile(params: {
    relPath: string;
    from?: number;
    lines?: number;
  }): Promise<{ text: string; path: string }> {
    const id = params.relPath.startsWith(MEM0_PATH_PREFIX)
      ? params.relPath.slice(MEM0_PATH_PREFIX.length)
      : params.relPath;
    const item = await this.provider.get(id);
    if (!item) throw new Error(`mem0: memory not found: ${id}`);
    let text = item.memory;
    if (params.from || params.lines) {
      const all = text.split("\n");
      // 1-based, matching the built-in MemorySearchManager convention
      const start = Math.max(1, params.from ?? 1);
      const count = Math.max(1, params.lines ?? all.length);
      text = all.slice(start - 1, start - 1 + count).join("\n");
    }
    return { text, path: params.relPath };
  }

  status(): MemoryProviderStatus {
    return {
      // SDK type is "builtin" | "qmd" — neither fits mem0; "builtin" is least wrong
      backend: "builtin",
      provider: "mem0",
      custom: { mode: this.cfg.mode, userId: this.effectiveUserId() },
    };
  }

  async probeEmbeddingAvailability(): Promise<MemoryEmbeddingProbeResult> {
    return { ok: true };
  }

  async probeVectorAvailability(): Promise<boolean> {
    return true;
  }

  async close(): Promise<void> {}
}

/** Build the payload for api.registerMemoryCapability(). */
export function createMemoryCapability(
  cfg: Mem0Config,
  provider: Mem0Provider,
  effectiveUserId: (sessionKey?: string) => string,
) {
  return {
    runtime: {
      async getMemorySearchManager() {
        return { manager: new Mem0SearchManager(provider, cfg, effectiveUserId) };
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
