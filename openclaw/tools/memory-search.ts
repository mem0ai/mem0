/**
 * memory_search tool — extracted from index.ts registerTools().
 *
 * Searches long-term and session-scoped memories stored in Mem0.
 * Supports scope filtering (session/long-term/all), categories,
 * advanced filters, and deduplication.
 */

import { Type } from "@sinclair/typebox";
import type {
  Mem0Config,
  Mem0Provider,
  MemoryItem,
  SearchOptions,
} from "../types.ts";

import type { ToolContext } from "./index.ts";

// ---------------------------------------------------------------------------
// Tool factory
// ---------------------------------------------------------------------------

/**
 * Creates the `memory_search` tool config object suitable for
 * `api.registerTool(config, { name })`.
 */
export function createMemorySearchTool(ctx: ToolContext) {
  const {
    cfg,
    provider,
    resolveUserId,
    getCurrentSessionId,
    buildSearchOptions,
  } = ctx;

  return {
    name: "memory_search",
    label: "Memory Search",
    description:
      "Search through long-term memories stored in Mem0. Use when you need context about user preferences, past decisions, or previously discussed topics.",
    parameters: Type.Object({
      query: Type.String({ description: "Search query" }),
      limit: Type.Optional(
        Type.Number({
          description: `Max results (default: ${cfg.topK})`,
        }),
      ),
      userId: Type.Optional(
        Type.String({
          description: "User ID to scope search (default: configured userId)",
        }),
      ),
      agentId: Type.Optional(
        Type.String({
          description:
            'Agent ID to search memories for a specific agent (e.g. "researcher"). Overrides userId.',
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
      categories: Type.Optional(
        Type.Array(Type.String(), {
          description:
            'Filter results by category (e.g. ["identity", "preference"]). Only returns memories tagged with these categories.',
        }),
      ),
      filters: Type.Optional(
        Type.Record(Type.String(), Type.Unknown(), {
          description:
            'Advanced filters object. Supports date ranges and metadata filtering. Examples: {"created_at": {"gte": "2026-03-01"}} for recent memories, {"AND": [{"categories": {"contains": "decision"}}, {"created_at": {"gte": "2026-01-01"}}]} for decisions this year. Operators: eq, ne, gt, gte, lt, lte, in, contains, icontains. Logical: AND, OR, NOT.',
        }),
      ),
      // --- NEW CLI-parity parameters ---
      rerank: Type.Optional(
        Type.Boolean({ description: "Enable reranking (platform only)" }),
      ),
      keyword: Type.Optional(
        Type.Boolean({ description: "Use keyword search instead of semantic" }),
      ),
      threshold: Type.Optional(
        Type.Number({ description: "Minimum similarity score (0-1)" }),
      ),
      topK: Type.Optional(
        Type.Number({ description: "Maximum number of results" }),
      ),
      fields: Type.Optional(
        Type.Array(Type.String(), {
          description: "Specific fields to return",
        }),
      ),
      enableGraph: Type.Optional(
        Type.Boolean({ description: "Enable graph memory in search" }),
      ),
    }),

    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const {
        query,
        limit,
        userId,
        agentId,
        scope = "all",
        categories: filterCategories,
        filters: agentFilters,
        // New CLI-parity params
        rerank,
        keyword,
        threshold,
        topK,
        fields,
        enableGraph,
      } = params as {
        query: string;
        limit?: number;
        userId?: string;
        agentId?: string;
        scope?: "session" | "long-term" | "all";
        categories?: string[];
        filters?: Record<string, unknown>;
        rerank?: boolean;
        keyword?: boolean;
        threshold?: number;
        topK?: number;
        fields?: string[];
        enableGraph?: boolean;
      };

      try {
        let results: MemoryItem[] = [];
        const uid = resolveUserId({ agentId, userId });
        const currentSessionId = getCurrentSessionId();

        // Apply agent-provided filters and new CLI-parity params to search options
        const applyFilters = (opts: SearchOptions): SearchOptions => {
          if (filterCategories?.length) opts.categories = filterCategories;
          if (agentFilters) opts.filters = agentFilters;
          // Pass through new CLI-parity parameters
          if (rerank !== undefined) opts.reranking = rerank;
          if (keyword !== undefined) opts.keyword_search = keyword;
          if (threshold !== undefined) opts.threshold = threshold;
          if (topK !== undefined) {
            opts.top_k = topK;
            opts.limit = topK;
          }
          // Note: 'fields' and 'enableGraph' are not in the legacy SearchOptions
          // type from types.ts. They are passed through for forward compatibility
          // when the backend supports them.
          if (fields !== undefined)
            (opts as unknown as Record<string, unknown>).fields = fields;
          if (enableGraph !== undefined)
            (opts as unknown as Record<string, unknown>).enable_graph =
              enableGraph;
          return opts;
        };

        if (scope === "session") {
          if (currentSessionId) {
            results = await provider!.search(
              query,
              applyFilters(buildSearchOptions(uid, limit, currentSessionId)),
            );
          }
        } else if (scope === "long-term") {
          results = await provider!.search(
            query,
            applyFilters(buildSearchOptions(uid, limit)),
          );
        } else {
          // "all" -- search both scopes and combine
          const longTermResults = await provider!.search(
            query,
            applyFilters(buildSearchOptions(uid, limit)),
          );
          let sessionResults: MemoryItem[] = [];
          if (currentSessionId) {
            sessionResults = await provider!.search(
              query,
              applyFilters(buildSearchOptions(uid, limit, currentSessionId)),
            );
          }
          // Deduplicate by ID, preferring long-term
          const seen = new Set(longTermResults.map((r) => r.id));
          results = [
            ...longTermResults,
            ...sessionResults.filter((r) => !seen.has(r.id)),
          ];
        }

        if (!results || results.length === 0) {
          return {
            content: [{ type: "text", text: "No relevant memories found." }],
            details: { count: 0 },
          };
        }

        const text = results
          .map(
            (r, i) =>
              `${i + 1}. ${r.memory} (score: ${((r.score ?? 0) * 100).toFixed(0)}%, id: ${r.id})`,
          )
          .join("\n");

        const sanitized = results.map((r) => ({
          id: r.id,
          memory: r.memory,
          score: r.score,
          categories: r.categories,
          created_at: r.created_at,
        }));

        return {
          content: [
            {
              type: "text",
              text: `Found ${results.length} memories:\n\n${text}`,
            },
          ],
          details: { count: results.length, memories: sanitized },
        };
      } catch (err) {
        return {
          content: [
            {
              type: "text",
              text: `Memory search failed: ${String(err)}`,
            },
          ],
          details: { error: String(err) },
        };
      }
    },
  };
}
