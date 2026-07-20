/**
 * Public Artifacts Provider for OpenClaw memory-wiki bridge mode.
 *
 * Exposes Mem0 memories and dream state as artifacts that can be
 * consumed by other plugins (e.g., memory-wiki in bridge mode).
 */

import type { Mem0Provider, MemoryItem, Mem0Config } from "./types.ts";
import type { MemoryArtifact } from "openclaw/plugin-sdk";
import { getDreamState } from "./dream-gate.ts";

export interface PublicArtifactsContext {
  provider: Mem0Provider;
  cfg: Mem0Config;
  stateDir?: string;
  effectiveUserId: (sessionKey?: string) => string;
}

/**
 * Create a publicArtifacts provider that exposes Mem0 data to other plugins.
 */
export function createPublicArtifactsProvider(ctx: PublicArtifactsContext) {
  return {
    async listArtifacts(options?: {
      userId?: string;
      types?: string[];
      limit?: number;
    }): Promise<MemoryArtifact[]> {
      const artifacts: MemoryArtifact[] = [];
      const userId = options?.userId ?? ctx.effectiveUserId();
      const types = options?.types ?? ["memory", "dream", "entity"];
      const limit = options?.limit ?? 100;

      try {
        // Memory artifacts
        if (types.includes("memory")) {
          const memories = await ctx.provider.getAll({
            user_id: userId,
            page_size: limit,
          });

          for (const mem of memories) {
            artifacts.push(memoryToArtifact(mem));
          }
        }

        // Dream state artifact (if dream enabled and stateDir available)
        if (types.includes("dream") && ctx.stateDir && ctx.cfg.skills?.dream?.enabled) {
          const dreamArtifact = getDreamArtifact(ctx.stateDir, userId);
          if (dreamArtifact) {
            artifacts.push(dreamArtifact);
          }
        }

        // Entity artifacts (grouped memories by category)
        if (types.includes("entity")) {
          const entityArtifacts = extractEntityArtifacts(artifacts.filter(a => a.type === "memory"));
          artifacts.push(...entityArtifacts);
        }

      } catch (err) {
        console.warn(
          "[mem0] publicArtifacts.listArtifacts failed:",
          err instanceof Error ? err.message : err,
        );
      }

      return artifacts.slice(0, limit);
    },
  };
}

/**
 * Convert a MemoryItem to a MemoryArtifact.
 */
function memoryToArtifact(mem: MemoryItem): MemoryArtifact {
  return {
    id: `mem0:memory:${mem.id}`,
    type: "memory",
    title: mem.memory.slice(0, 80) + (mem.memory.length > 80 ? "..." : ""),
    content: mem.memory,
    metadata: {
      score: mem.score,
      categories: mem.categories,
      user_id: mem.user_id,
      ...mem.metadata,
    },
    createdAt: mem.created_at,
    updatedAt: mem.updated_at,
  };
}

/**
 * Get dream consolidation state as an artifact.
 */
function getDreamArtifact(stateDir: string, userId: string): MemoryArtifact | null {
  try {
    const state = getDreamState(stateDir);
    if (state.lastConsolidatedAt === 0) {
      return null; // No consolidation has occurred yet
    }

    const lastDate = new Date(state.lastConsolidatedAt).toISOString();
    return {
      id: `mem0:dream:${userId}:state`,
      type: "dream",
      title: `Dream State (last: ${lastDate.split("T")[0]})`,
      content: [
        `Last consolidation: ${lastDate}`,
        `Sessions since: ${state.sessionsSince}`,
        `Last session: ${state.lastSessionId ?? "none"}`,
      ].join("\n"),
      metadata: {
        lastConsolidatedAt: state.lastConsolidatedAt,
        sessionsSince: state.sessionsSince,
        lastSessionId: state.lastSessionId,
        user_id: userId,
      },
      updatedAt: lastDate,
    };
  } catch {
    return null;
  }
}

/**
 * Extract entity artifacts from memories (grouped by category).
 */
function extractEntityArtifacts(memoryArtifacts: MemoryArtifact[]): MemoryArtifact[] {
  const byCategory = new Map<string, MemoryArtifact[]>();

  for (const artifact of memoryArtifacts) {
    const categories = (artifact.metadata?.categories as string[]) ?? ["uncategorized"];
    for (const cat of categories) {
      const existing = byCategory.get(cat) ?? [];
      existing.push(artifact);
      byCategory.set(cat, existing);
    }
  }

  const entities: MemoryArtifact[] = [];
  for (const [category, mems] of byCategory) {
    if (mems.length >= 2) {
      entities.push({
        id: `mem0:entity:${category}`,
        type: "entity",
        title: `${category.charAt(0).toUpperCase() + category.slice(1)} (${mems.length} memories)`,
        content: mems.map(m => `- ${m.content}`).join("\n"),
        metadata: {
          category,
          memoryCount: mems.length,
          memoryIds: mems.map(m => m.id),
        },
      });
    }
  }

  return entities;
}
