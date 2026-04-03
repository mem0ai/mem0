/**
 * memory_list tool — extracted from index.ts registerTools().
 *
 * Lists all stored memories for a user or agent. Supports scope filtering
 * (session/long-term/all), deduplication, and CLI-parity parameters for
 * pagination, category filtering, date ranges, and graph support.
 */

import { Type } from "@sinclair/typebox";
import type { Mem0Config, Mem0Provider, MemoryItem } from "../types.ts";

import type { ListOptions } from "../types.ts";
import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_list` tool config object suitable for
 * `api.registerTool(config, { name })`.
 */
export function createMemoryListTool(ctx: ToolContext) {
  const { provider, resolveUserId, getCurrentSessionId } = ctx;

  return {
    name: "memory_list",
    label: "Memory List",
    description:
      "List all stored memories for a user or agent. Use this when you want to see everything that's been remembered, rather than searching for something specific.",
    parameters: Type.Object({
      userId: Type.Optional(
        Type.String({
          description:
            "User ID to list memories for (default: configured userId)",
        }),
      ),
      agentId: Type.Optional(
        Type.String({
          description:
            'Agent ID to list memories for a specific agent (e.g. "researcher"). Overrides userId.',
        }),
      ),
      scope: Type.Optional(
        Type.Union(
          [
            Type.Literal("session"),
            Type.Literal("long-term"),
            Type.Literal("all"),
          ],
          {
            description:
              'Memory scope: "session" (current session only), "long-term" (user-scoped only), or "all" (both). Default: "all"',
          },
        ),
      ),
      // --- NEW CLI-parity parameters ---
      page: Type.Optional(
        Type.Number({ description: "Page number (default: 1)" }),
      ),
      pageSize: Type.Optional(
        Type.Number({ description: "Results per page (default: 100)" }),
      ),
      category: Type.Optional(
        Type.String({ description: "Filter by category" }),
      ),
      after: Type.Optional(
        Type.String({ description: "Created after date (YYYY-MM-DD)" }),
      ),
      before: Type.Optional(
        Type.String({ description: "Created before date (YYYY-MM-DD)" }),
      ),
      enableGraph: Type.Optional(
        Type.Boolean({ description: "Enable graph in listing" }),
      ),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const {
        userId,
        agentId,
        scope = "all",
        // New CLI-parity params
        page,
        pageSize,
        category,
        after,
        before,
        enableGraph,
      } = params as {
        userId?: string;
        agentId?: string;
        scope?: "session" | "long-term" | "all";
        page?: number;
        pageSize?: number;
        category?: string;
        after?: string;
        before?: string;
        enableGraph?: boolean;
      };

      try {
        let memories: MemoryItem[] = [];
        const uid = resolveUserId({ agentId, userId });
        const currentSessionId = getCurrentSessionId();

        // Build base options for getAll, incorporating new CLI-parity params
        const buildGetAllOpts = (extra?: { run_id?: string }): ListOptions => {
          const opts: Record<string, unknown> = {
            user_id: uid,
            source: "OPENCLAW",
          };
          if (extra?.run_id) opts.run_id = extra.run_id;
          if (pageSize !== undefined) opts.page_size = pageSize;
          if (page !== undefined) opts.page = page;
          if (category !== undefined) opts.category = category;
          if (after !== undefined) opts.after = after;
          if (before !== undefined) opts.before = before;
          if (enableGraph !== undefined) opts.enable_graph = enableGraph;
          return opts as unknown as ListOptions;
        };

        if (scope === "session") {
          if (currentSessionId) {
            memories = await provider!.getAll(
              buildGetAllOpts({ run_id: currentSessionId }),
            );
          }
        } else if (scope === "long-term") {
          memories = await provider!.getAll(buildGetAllOpts());
        } else {
          // "all" — combine both scopes
          const longTerm = await provider!.getAll(buildGetAllOpts());
          let session: MemoryItem[] = [];
          if (currentSessionId) {
            session = await provider!.getAll(
              buildGetAllOpts({ run_id: currentSessionId }),
            );
          }
          const seen = new Set(longTerm.map((r) => r.id));
          memories = [...longTerm, ...session.filter((r) => !seen.has(r.id))];
        }

        if (!memories || memories.length === 0) {
          return {
            content: [{ type: "text", text: "No memories stored yet." }],
            details: { count: 0 },
          };
        }

        const text = memories
          .map((r, i) => `${i + 1}. ${r.memory} (id: ${r.id})`)
          .join("\n");

        const sanitized = memories.map((r) => ({
          id: r.id,
          memory: r.memory,
          categories: r.categories,
          created_at: r.created_at,
        }));

        return {
          content: [
            {
              type: "text",
              text: `${memories.length} memories:\n\n${text}`,
            },
          ],
          details: { count: memories.length, memories: sanitized },
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: `Memory list failed: ${String(err)}`,
            },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
