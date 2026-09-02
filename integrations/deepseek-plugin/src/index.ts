/**
 * deepseek-plugin: Mem0 long-term memory as a native DeepSeek Harness (Cordis) plugin.
 *
 * Registers two agent-callable tools backed by the Mem0 SDK:
 *   - `search_memory` recalls facts relevant to a query
 *   - `add_memory` stores a fact for future sessions
 *
 * A plugin is a Cordis module that exports `apply(ctx, config)`. Declaring
 * `inject = ['tools']` holds the plugin until the harness tool registry exists;
 * tools registered via `ctx.tools.register(...)` are auto-unregistered when the
 * plugin unmounts (Cordis revertible effects).
 */
import type { Context } from "@deepseek-ai/cordis";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { MemoryClient } from "mem0ai";
import { formatMemoryList, formatAddResult } from "./formatting.ts";
import { truncateOutput } from "./output.ts";
import { resolveSearchFilters, resolveAddParams } from "./scoping.ts";
import { captureEvent, errorKind } from "./telemetry.ts";

export const name = "mem0";
export const inject = ["tools"];

// Tags writes so Mem0's backend attributes them to this integration in
// telemetry. The backend keeps recognized values via its KNOWN_EVENT_SOURCES
// allowlist; unknown values bucket into "OTHERS", so "DEEPSEEK_HARNESS" must be
// added to that allowlist for usage to surface by name (a one-line backend PR,
// same pattern as the ZAPIER / STRANDS sources).
const SOURCE = "DEEPSEEK_HARNESS";

const DEFAULT_SEARCH_LIMIT = 10;

export interface Config {
  /** Mem0 API key. Defaults to the MEM0_API_KEY env var. */
  apiKey?: string;
  /** Default entity that owns the memories (Mem0 user scope). */
  userId: string;
  /** Optional Mem0 Platform base-URL override (on-prem / dedicated); defaults to api.mem0.ai. Not a switch to self-hosted OSS. */
  host?: string;
}

// Both tools return a single text string; the render is identical, so lift it
// into one shared declaration instead of repeating the block per tool.
const textOutput = {
  schema: { type: "string" } as const,
  render: (_args: unknown, value: string) => [
    { type: "text" as const, text: value },
  ],
};

// Optional per-call scoping params, shared by both tools. A single harness
// install can serve more than one entity, so the model may override the
// mount-time default per call (see scoping.ts).
const scopeParams = {
  userId: {
    type: "string",
    description:
      "Entity that owns the memory. Defaults to the plugin's configured userId; set this only to read or write another user's memories.",
  },
  agentId: {
    type: "string",
    description: "Optional agent scope, to partition memories by agent.",
  },
  runId: {
    type: "string",
    description: "Optional run/session scope, to partition memories by session.",
  },
} as const;

export function apply(ctx: Context, config: Config): void {
  const apiKey = config.apiKey ?? process.env.MEM0_API_KEY;
  if (!apiKey) {
    throw new Error("deepseek-plugin: set config.apiKey or the MEM0_API_KEY env var");
  }
  const userId = config.userId;
  if (!userId) {
    throw new Error("deepseek-plugin: config.userId is required");
  }

  const client = new MemoryClient({
    apiKey,
    ...(config.host ? { host: config.host } : {}),
  });

  captureEvent("deepseek.plugin.mounted", { has_host: Boolean(config.host) }, client);

  // Recall. The platform rejects top-level entity params on search, so scope
  // goes inside `filters` (unlike add below, which takes them top-level).
  ctx.tools.register(
    defineTool({
      name: "search_memory",
      description:
        "Search the user's long-term Mem0 memory for facts relevant to a query. Use proactively before answering anything that may depend on what the user told you earlier.",
      parameters: {
        query: { type: "string", description: "What to recall.", required: true },
        limit: {
          type: "integer",
          description: `Max results to return (default ${DEFAULT_SEARCH_LIMIT}).`,
        },
        ...scopeParams,
      },
      output: textOutput,
      async execute({ query, limit, userId: u, agentId, runId }) {
        const filters = resolveSearchFilters({ userId: u, agentId, runId }, userId);
        const topK = limit && limit > 0 ? limit : DEFAULT_SEARCH_LIMIT;
        const started = Date.now();
        try {
          const { results } = await client.search(query, { filters, topK });
          captureEvent(
            "deepseek.tool.search_memory",
            {
              success: true,
              duration_ms: Date.now() - started,
              top_k: topK,
              result_count: results?.length ?? 0,
              query_chars: query.length,
              scope_overridden: Boolean(u && u !== userId),
              has_agent_id: Boolean(agentId),
              has_run_id: Boolean(runId),
            },
            client,
          );
          return truncateOutput(formatMemoryList(results ?? []));
        } catch (err) {
          captureEvent(
            "deepseek.tool.search_memory",
            {
              success: false,
              duration_ms: Date.now() - started,
              top_k: topK,
              error_kind: errorKind(err),
            },
            client,
          );
          return `search_memory failed: ${err instanceof Error ? err.message : String(err)}`;
        }
      },
    }),
  );

  // Write. `source` tags the memory for telemetry attribution.
  ctx.tools.register(
    defineTool({
      name: "add_memory",
      description:
        "Store a fact in the user's long-term Mem0 memory for later sessions. Extraction runs asynchronously server-side, so a stored fact may take a moment to become searchable; do not immediately search to confirm the write.",
      parameters: {
        text: { type: "string", description: "The fact to remember.", required: true },
        ...scopeParams,
      },
      output: textOutput,
      async execute({ text, userId: u, agentId, runId }) {
        const addParams = resolveAddParams({ userId: u, agentId, runId }, userId);
        const started = Date.now();
        try {
          const result = await client.add([{ role: "user", content: text }], {
            ...addParams,
            source: SOURCE,
          });
          captureEvent(
            "deepseek.tool.add_memory",
            {
              success: true,
              duration_ms: Date.now() - started,
              text_chars: text.length,
              memory_count: Array.isArray(result) ? result.length : 0,
              scope_overridden: Boolean(u && u !== userId),
              has_agent_id: Boolean(agentId),
              has_run_id: Boolean(runId),
            },
            client,
          );
          return truncateOutput(formatAddResult(result));
        } catch (err) {
          captureEvent(
            "deepseek.tool.add_memory",
            {
              success: false,
              duration_ms: Date.now() - started,
              text_chars: text.length,
              error_kind: errorKind(err),
            },
            client,
          );
          return `add_memory failed: ${err instanceof Error ? err.message : String(err)}`;
        }
      },
    }),
  );
}
