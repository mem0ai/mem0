/**
 * Public Artifacts Provider for OpenClaw memory-wiki bridge mode.
 *
 * Exposes Mem0 memories as artifacts that can be
 * consumed by other plugins (e.g., memory-wiki in bridge mode).
 */

import type { Mem0Provider, MemoryItem } from "./types.ts";
import type { MemoryArtifact } from "openclaw/plugin-sdk";

export interface PublicArtifactsContext {
  provider: Mem0Provider;
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
      const types = options?.types ?? ["memory", "entity"];
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
