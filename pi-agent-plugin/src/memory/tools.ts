import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { StringEnum } from "@earendil-works/pi-ai";
import type MemoryClient from "mem0ai";
import type { Scope, ScopeContext, Mem0Config } from "../types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "../types.ts";
import { resolveSearchFilters, resolveAddParams } from "./scoping.ts";
import { formatMemoryList } from "./formatting.ts";
import { captureToolEvent } from "../telemetry.ts";

const MAX_OUTPUT_LINES = 200;
const MAX_OUTPUT_BYTES = 50_000;

function truncateOutput(text: string): string {
  const lines = text.split("\n");
  if (lines.length <= MAX_OUTPUT_LINES && text.length <= MAX_OUTPUT_BYTES) {
    return text;
  }

  const kept = lines.slice(0, MAX_OUTPUT_LINES);
  let result = kept.join("\n");
  if (result.length > MAX_OUTPUT_BYTES) {
    result = result.slice(0, MAX_OUTPUT_BYTES);
  }

  const dropped = lines.length - kept.length;
  if (dropped > 0 || text.length > MAX_OUTPUT_BYTES) {
    result += `\n\n[Output truncated: showing ${kept.length} of ${lines.length} lines]`;
  }
  return result;
}

interface ToolParams {
  action: "search" | "add" | "get_all" | "delete" | "delete_all";
  query?: string;
  content?: string;
  memory_id?: string;
  scope?: Scope;
}

export function buildToolExecute(
  mem0: MemoryClient,
  scopeCtx: ScopeContext,
  defaultScope: Scope,
) {
  return async (params: ToolParams, signal?: AbortSignal) => {
    const scope = params.scope ?? defaultScope;

    switch (params.action) {
      case "search": {
        if (signal?.aborted) throw new Error("Cancelled");
        if (!params.query) throw new Error("query is required for search");
        const filters = resolveSearchFilters(scope, scopeCtx);
        const result = await mem0.search(params.query, { filters });
        const memories = result.results ?? [];
        return {
          content: [{ type: "text" as const, text: truncateOutput(formatMemoryList(memories)) }],
          details: { matchCount: memories.length },
        };
      }

      case "add": {
        if (signal?.aborted) throw new Error("Cancelled");
        if (!params.content) throw new Error("content is required for add");
        const addParams = resolveAddParams(scope, scopeCtx);
        const result = await mem0.add(
          [{ role: "user", content: params.content }],
          { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES },
        );
        const res = result as any;
        const msg = res.message ?? "Memory stored.";
        return {
          content: [{ type: "text" as const, text: msg }],
          details: { eventId: res.eventId ?? null, status: res.status ?? null },
        };
      }

      case "get_all": {
        if (signal?.aborted) throw new Error("Cancelled");
        const filters = resolveSearchFilters(scope, scopeCtx);
        const result = await mem0.getAll({ filters });
        const memories = result.results ?? [];
        return {
          content: [{ type: "text" as const, text: truncateOutput(formatMemoryList(memories)) }],
          details: { totalCount: result.count ?? memories.length },
        };
      }

      case "delete": {
        if (signal?.aborted) throw new Error("Cancelled");
        if (!params.memory_id) throw new Error("memory_id is required for delete");
        const result = await mem0.delete(params.memory_id);
        return {
          content: [{ type: "text" as const, text: result.message ?? "Memory deleted." }],
          details: {},
        };
      }

      case "delete_all": {
        if (signal?.aborted) throw new Error("Cancelled");
        const delParams = resolveAddParams(scope, scopeCtx);
        const result = await mem0.deleteAll(delParams);
        return {
          content: [{ type: "text" as const, text: result.message ?? "All memories deleted." }],
          details: {},
        };
      }
    }
  };
}

export function registerMemoryTool(
  pi: ExtensionAPI,
  mem0: MemoryClient,
  config: Mem0Config,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
): void {
  pi.registerTool({
    name: "mem0_memory",
    label: "Mem0 Memory",
    description:
      "Search, add, and manage persistent semantic memories powered by Mem0. Memories persist across sessions and devices. Output is truncated to 200 lines / 50KB.",
    promptSnippet: "Semantic memory search and storage via Mem0",
    promptGuidelines: [
      'Use mem0_memory with action "search" when the user asks about past conversations, preferences, or decisions',
      'Use mem0_memory with action "add" to save important facts, preferences, goals, decisions, or lessons the user shares',
      "Always use the default project scope unless the user EXPLICITLY asks to search across all projects — only then use scope \"global\"",
      "Do NOT pass scope at all for normal queries — omitting it uses the project default automatically",
    ],
    parameters: Type.Object({
      action: StringEnum([
        "search",
        "add",
        "get_all",
        "delete",
        "delete_all",
      ] as const),
      query: Type.Optional(
        Type.String({ description: "Search query or memory text" }),
      ),
      content: Type.Optional(
        Type.String({ description: "Memory content to store" }),
      ),
      memory_id: Type.Optional(
        Type.String({ description: "Memory ID for delete" }),
      ),
      scope: Type.Optional(
        StringEnum(["project", "session", "global"] as const),
      ),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const scopeCtx = getScopeCtx();
      const exec = buildToolExecute(mem0, scopeCtx, config.defaultScope);
      const start = Date.now();
      try {
        const result = await exec(params as ToolParams, signal);
        const details = (result as any).details ?? {};
        captureToolEvent((params as ToolParams).action, {
          success: true,
          latency_ms: Date.now() - start,
          result_count: details.matchCount ?? details.totalCount ?? undefined,
        }, telemetryCtx);
        return result;
      } catch (err) {
        captureToolEvent((params as ToolParams).action, {
          success: false,
          latency_ms: Date.now() - start,
          error_type: err instanceof Error ? err.name : "unknown",
        }, telemetryCtx);
        throw err;
      }
    },
  });
}
