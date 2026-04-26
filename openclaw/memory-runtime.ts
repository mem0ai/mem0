/**
 * Memory Runtime Adapter for OpenClaw plugin capability registration.
 *
 * Provides the runtime interface expected by OpenClaw's memory capability system.
 */

import type { Mem0Provider, Mem0Config } from "./types.ts";
import type { Backend } from "./backend/base.ts";

export interface RuntimeContext {
  provider: Mem0Provider;
  cfg: Mem0Config;
  backend: Backend;
}

export function createMemoryRuntime(ctx: RuntimeContext) {
  return {
    getMemorySearchManager: async (params: any) => {
      return {
        manager: {
          status: async () => {
            try {
              await ctx.provider.search("ping", { top_k: 1, user_id: "system-health-probe" });
              return { ok: true, embedding: { ok: true } };
            } catch (error) {
              return { ok: false, embedding: { ok: false, error: String(error) } };
            }
          },
          probeEmbeddingAvailability: async () => true,
          close: async () => {},
        },
      };
    },
    resolveMemoryBackendConfig: (params: any) => ctx.cfg,
    closeAllMemorySearchManagers: async () => {},
  };
}
