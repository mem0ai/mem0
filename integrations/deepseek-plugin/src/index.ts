/**
 * deepseek-plugin: Mem0 long-term memory as a native DeepSeek Harness (Cordis) plugin.
 *
 * Registers two agent-callable tools backed by the Mem0 SDK:
 *   - `search_memory` recalls facts relevant to a query
 *   - `add_memory` stores a fact for future sessions
 *
 * A plugin is a Cordis module that exports `apply(ctx, config)`. Declaring
 * `inject = ['tools', 'systemPrompt']` holds the plugin until the harness services exist;
 * tools registered via `ctx.tools.register(...)` are auto-unregistered when the
 * plugin unmounts (Cordis revertible effects).
 */
import type { Context } from "@deepseek-ai/cordis";
import type {} from "@deepseek-ai/dsh-agent";
import type { PromptAssembly } from "@deepseek-ai/dsh-system-prompt";
import type {} from "@deepseek-ai/dsh-session";
import { defineTool } from "@deepseek-ai/dsh-tools";
import { MemoryClient } from "mem0ai";
import { formatMemoryList, formatAddResult } from "./formatting.ts";
import { truncateOutput } from "./output.ts";
import { resolveSearchFilters, resolveAddParams } from "./scoping.ts";
import { captureEvent, errorKind } from "./telemetry.ts";
import { createMemoryLifecycle } from "../../agent-plugin-core/typescript/src/lifecycle.ts";

export const name = "mem0";
export const inject = ["tools", "systemPrompt"];

// Tags writes so Mem0's backend attributes them to this integration in
// telemetry. The backend keeps recognized values via its KNOWN_EVENT_SOURCES
// allowlist; unknown values bucket into "OTHERS", so "DEEPSEEK_HARNESS" must be
// added to that allowlist for usage to surface by name (a one-line backend PR,
// same pattern as the ZAPIER / STRANDS sources).
const SOURCE = "DEEPSEEK_HARNESS";

const DEFAULT_SEARCH_LIMIT = 10;
const AUTO_RECALL_LIMIT = 5;

interface HarnessMessage {
  role: string;
  content?: unknown;
  source?: { kind?: string };
}

interface SessionState {
  lifecycle: ReturnType<typeof createMemoryLifecycle>;
  messages: HarnessMessage[];
}

export interface Config {
  /** Mem0 API key. Defaults to the MEM0_API_KEY env var. */
  apiKey?: string;
  /** Default entity that owns the memories (Mem0 user scope). */
  userId: string;
  /** Optional Mem0 Platform base-URL override (on-prem / dedicated); defaults to api.mem0.ai. Not a switch to self-hosted OSS. */
  host?: string;
  /** Recall relevant memory before each model request. Defaults to true. */
  autoRecall?: boolean;
  /** Store completed turns automatically. Defaults to true. */
  autoCapture?: boolean;
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
  const toolLifecycle = createMemoryLifecycle();
  const sessionStates = new WeakMap<object, SessionState>();
  const stateFor = (session: object): SessionState => {
    let state = sessionStates.get(session);
    if (!state) {
      const lifecycle = createMemoryLifecycle();
      lifecycle.beginSession();
      state = { lifecycle, messages: [] };
      sessionStates.set(session, state);
    }
    return state;
  };

  captureEvent("deepseek.plugin.mounted", {
    has_host: Boolean(config.host),
    auto_recall: config.autoRecall !== false,
    auto_capture: config.autoCapture !== false,
  }, client);

  if (config.autoRecall !== false) {
    ctx.on("system-prompt/assemble", async (_input, context, next): Promise<PromptAssembly> => {
      const assembly = await next();
      const { agent, signal } = context;
      if (!agent || signal?.aborted) return assembly;

      const state = stateFor(agent.session);
      const prompt = state.lifecycle.prepareConversation(
        agent.session
          .deriveMessages()
          .filter((message) => message.role === "user" && message.source?.kind === "user"),
      ).at(-1)?.content;
      if (!prompt) return assembly;

      const memoryContext = await state.lifecycle.recall(prompt, true, async (query) => {
        const started = Date.now();
        try {
          const result = await client.search(query, {
            filters: resolveSearchFilters({}, userId),
            topK: AUTO_RECALL_LIMIT,
          });
          captureEvent("deepseek.recall.auto", {
            success: true,
            duration_ms: Date.now() - started,
            result_count: result.results?.length ?? 0,
          }, client);
          return result;
        } catch (err) {
          captureEvent("deepseek.recall.auto", {
            success: false,
            duration_ms: Date.now() - started,
            error_kind: errorKind(err),
          }, client);
          throw err;
        }
      });
      if (!memoryContext || signal?.aborted) return assembly;
      return {
        ...assembly,
        contexts: [...assembly.contexts, { name: "mem0:recall", text: memoryContext }],
      };
    });
  }

  if (config.autoCapture !== false) {
    ctx.on("session/event", (session, event) => {
      const state = stateFor(session);
      if (event.type === "turn/start") {
        state.messages = [];
      } else if (event.type === "user/message" && event.data.source.kind === "user") {
        state.messages.push(event.data);
      } else if (event.type === "assistant/message") {
        state.messages.push(event.data.message);
      } else if (event.type === "turn/end") {
        const conversation = state.lifecycle.prepareConversation(state.messages);
        state.messages = [];
        if (event.data.reason.kind !== "completed" || conversation.length === 0) return;
        void client
          .add(conversation, { userId, source: SOURCE })
          .then(() => captureEvent("deepseek.capture.auto", {
            success: true,
            message_count: conversation.length,
          }, client))
          .catch((err: unknown) => captureEvent("deepseek.capture.auto", {
            success: false,
            error_kind: errorKind(err),
          }, client));
      }
    });
  }

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
        const safeQuery = toolLifecycle.prepareUserText(query);
        const filters = resolveSearchFilters({ userId: u, agentId, runId }, userId);
        const topK = limit && limit > 0 ? limit : DEFAULT_SEARCH_LIMIT;
        const started = Date.now();
        try {
          const { results } = await client.search(safeQuery, { filters, topK });
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
          const result = await client.add(
            [{ role: "user", content: toolLifecycle.prepareUserText(text) }],
            {
              ...addParams,
              source: SOURCE,
            },
          );
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
