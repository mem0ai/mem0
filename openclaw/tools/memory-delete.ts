/**
 * memory_delete tool — unified delete tool replacing memory_forget and memory_delete_all.
 *
 * Supports four modes:
 *   1. By memory_id — direct deletion of a specific memory
 *   2. By query — search-and-delete (auto-deletes high-confidence match, otherwise lists candidates)
 *   3. all:true — bulk-delete all memories for a user (requires confirm:true)
 *   4. entity:true — cascade-delete an entity and all its memories (requires confirm:true, platform only)
 */

import { Type } from "@sinclair/typebox";
import { isSubagentSession } from "../isolation.ts";

import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_delete` tool config object suitable for
 * `api.registerTool(config, { name })`.
 *
 * This replaces both `memory_forget` and `memory_delete_all` from the
 * original index.ts implementation.
 */
export function createMemoryDeleteTool(ctx: ToolContext) {
  const {
    api,
    provider,
    resolveUserId,
    getCurrentSessionId,
    buildSearchOptions,
    backend,
  } = ctx;

  return {
    name: "memory_delete",
    label: "Memory Delete",
    description:
      "Delete memories from Mem0. Provide a specific memoryId for direct deletion, a query to search and delete, all:true for bulk deletion, or entity:true to cascade-delete an entity. Bulk operations require confirm:true. GDPR-compliant.",
    parameters: Type.Object({
      memory_id: Type.Optional(
        Type.String({ description: "Specific memory ID to delete" }),
      ),
      query: Type.Optional(
        Type.String({
          description:
            "Search query to find memory to delete (searches and deletes best match)",
        }),
      ),
      all: Type.Optional(
        Type.Boolean({
          description:
            "Delete ALL memories matching scope filters. Requires confirm: true",
        }),
      ),
      entity: Type.Optional(
        Type.Boolean({
          description:
            "Delete entity and all its memories (cascade). Requires confirm: true",
        }),
      ),
      confirm: Type.Optional(
        Type.Boolean({
          description:
            "Must be true for bulk operations (all/entity). Safety gate.",
        }),
      ),
      user_id: Type.Optional(Type.String({ description: "Scope to user" })),
      agent_id: Type.Optional(Type.String({ description: "Scope to agent" })),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const { memory_id, query, all, entity, confirm, user_id, agent_id } =
        params as {
          memory_id?: string;
          query?: string;
          all?: boolean;
          entity?: boolean;
          confirm?: boolean;
          user_id?: string;
          agent_id?: string;
        };

      try {
        // Block subagent deletes at the tool level.
        const currentSessionId = getCurrentSessionId();
        if (isSubagentSession(currentSessionId)) {
          api.logger.warn(
            "openclaw-mem0: blocked memory_delete from subagent session",
          );
          return {
            content: [
              {
                type: "text",
                text: "Memory deletion is not available in subagent sessions. The main agent handles memory.",
              },
            ],
            details: { error: "subagent_blocked" },
          };
        }

        // Mode 1: Delete by specific memory ID
        if (memory_id) {
          await provider!.delete(memory_id);
          return {
            content: [{ type: "text", text: `Memory ${memory_id} deleted.` }],
            details: { action: "deleted", id: memory_id },
          };
        }

        // Mode 2: Search-and-delete by query
        if (query) {
          const uid = resolveUserId({ agentId: agent_id, userId: user_id });
          const results = await provider!.search(
            query,
            buildSearchOptions(uid, 5),
          );

          if (!results || results.length === 0) {
            return {
              content: [{ type: "text", text: "No matching memories found." }],
              details: { found: 0 },
            };
          }

          // If single high-confidence match, delete directly
          if (results.length === 1 || (results[0].score ?? 0) > 0.9) {
            await provider!.delete(results[0].id);
            return {
              content: [
                {
                  type: "text",
                  text: `Deleted: "${results[0].memory}"`,
                },
              ],
              details: { action: "deleted", id: results[0].id },
            };
          }

          // Multiple ambiguous results — return candidates for user to pick
          const list = results
            .map(
              (r) =>
                `- [${r.id}] ${r.memory.slice(0, 80)}${r.memory.length > 80 ? "..." : ""} (score: ${((r.score ?? 0) * 100).toFixed(0)}%)`,
            )
            .join("\n");

          const candidates = results.map((r) => ({
            id: r.id,
            memory: r.memory,
            score: r.score,
          }));

          return {
            content: [
              {
                type: "text",
                text: `Found ${results.length} candidates. Specify memory_id to delete:\n${list}`,
              },
            ],
            details: { action: "candidates", candidates },
          };
        }

        // Mode 3: Bulk-delete all memories for a user
        if (all) {
          if (!confirm) {
            return {
              content: [
                {
                  type: "text",
                  text: "Bulk deletion requires confirm: true. Ask the user to confirm before proceeding.",
                },
              ],
              details: { error: "confirmation_required" },
            };
          }

          const uid = resolveUserId({ agentId: agent_id, userId: user_id });
          await provider!.deleteAll(uid);
          api.logger.info(
            `openclaw-mem0: deleted all memories for user ${uid}`,
          );
          return {
            content: [
              {
                type: "text",
                text: `All memories deleted for user "${uid}".`,
              },
            ],
            details: { action: "deleted_all", user_id: uid },
          };
        }

        // Mode 4: Cascade-delete entity (platform only)
        if (entity) {
          if (!confirm) {
            return {
              content: [
                {
                  type: "text",
                  text: "Entity deletion requires confirm: true. Ask the user to confirm before proceeding.",
                },
              ],
              details: { error: "confirmation_required" },
            };
          }

          const entityOpts: { userId?: string; agentId?: string } = {};
          if (user_id) entityOpts.userId = user_id;
          if (agent_id) entityOpts.agentId = agent_id;

          await backend.deleteEntities(entityOpts);
          api.logger.info(
            `openclaw-mem0: deleted entity (userId=${user_id ?? "default"}, agentId=${agent_id ?? "none"})`,
          );
          return {
            content: [
              {
                type: "text",
                text: `Entity and all associated memories deleted (userId=${user_id ?? "default"}, agentId=${agent_id ?? "none"}).`,
              },
            ],
            details: {
              action: "entity_deleted",
              user_id: user_id ?? "default",
              agent_id: agent_id,
            },
          };
        }

        // No valid mode specified
        return {
          content: [
            {
              type: "text",
              text: "Provide memory_id, query, all, or entity to specify what to delete.",
            },
          ],
          details: { error: "missing_param" },
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: `Memory delete failed: ${String(err)}`,
            },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
