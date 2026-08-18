/**
 * dsh-mem0: Mem0 long-term memory as a native DeepSeek Harness (Cordis) plugin.
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

export const name = "mem0";
export const inject = ["tools"];

// Tags writes so Mem0's backend attributes them to this integration in
// telemetry. The backend keeps recognized values via its KNOWN_EVENT_SOURCES
// allowlist; unknown values bucket into "OTHERS", so "DEEPSEEK_HARNESS" must be
// added to that allowlist for usage to surface by name (a one-line backend PR,
// same pattern as the ZAPIER / STRANDS sources).
const SOURCE = "DEEPSEEK_HARNESS";

export interface Config {
  /** Mem0 API key. Defaults to the MEM0_API_KEY env var. */
  apiKey?: string;
  /** Entity that owns the memories (Mem0 user scope). */
  userId: string;
  /** Optional Mem0 host override, e.g. a self-hosted or local sandbox URL. */
  host?: string;
}

export function apply(ctx: Context, config: Config): void {
  const apiKey = config.apiKey ?? process.env.MEM0_API_KEY;
  if (!apiKey) {
    throw new Error("dsh-mem0: set config.apiKey or the MEM0_API_KEY env var");
  }
  const userId = config.userId;
  if (!userId) {
    throw new Error("dsh-mem0: config.userId is required");
  }

  const client = new MemoryClient({
    apiKey,
    ...(config.host ? { host: config.host } : {}),
  });

  // Recall. The platform rejects top-level entity params on search, so scope
  // goes inside `filters` (unlike add below, which takes user_id top-level).
  ctx.tools.register(
    defineTool({
      name: "search_memory",
      description:
        "Search the user's long-term Mem0 memory for facts relevant to a query.",
      parameters: {
        query: { type: "string", description: "What to recall.", required: true },
      },
      output: {
        schema: { type: "string" },
        render: (_args, value) => [{ type: "text", text: value }],
      },
      async execute({ query }) {
        const results = await client.search(query, {
          filters: { user_id: userId },
        });
        return JSON.stringify(results, null, 2);
      },
    }),
  );

  // Write. `source` tags the memory for telemetry attribution.
  ctx.tools.register(
    defineTool({
      name: "add_memory",
      description:
        "Store a fact in the user's long-term Mem0 memory for later sessions.",
      parameters: {
        text: { type: "string", description: "The fact to remember.", required: true },
      },
      output: {
        schema: { type: "string" },
        render: (_args, value) => [{ type: "text", text: value }],
      },
      async execute({ text }) {
        const result = await client.add([{ role: "user", content: text }], {
          user_id: userId,
          source: SOURCE,
        });
        return JSON.stringify(result);
      },
    }),
  );
}
