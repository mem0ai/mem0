import { resolveToolScope } from "../agent-plugin-core/typescript/src/scoping.ts";
// Mem0 memory plugin for OpenCode: captures and recalls memories across sessions
// (add / search / manage) via the Mem0 platform, wired through OpenCode plugin hooks.
// Memory operations are exposed as native OpenCode tools backed by the mem0ai SDK
// (no MCP server required).
import type {Plugin} from "@opencode-ai/plugin";
import {tool} from "@opencode-ai/plugin";
import {MemoryClient} from "mem0ai";
import {userInfo} from "os";
import {resolve, dirname} from "path";
import {randomBytes} from "crypto";
import {existsSync, readFileSync, readdirSync} from "fs";
import {homedir} from "os";
import {join} from "path";
import {captureEvent} from "./telemetry";
import {asScope, scopeSearchFilters, scopeWriteParams, resolveDefaultScope, type Scope} from "./scope";
import {resolveApiKey} from "./api-key";
import {
  createMemoryLifecycle,
  RECALL_TOP_K,
  repoCaptureOptions,
  type ConversationMessage,
} from "../agent-plugin-core/typescript/src/lifecycle.ts";
import {resolveRepoContext} from "../agent-plugin-core/typescript/src/identity.ts";
import {SEARCH_QUERY_DESCRIPTION, SEARCH_TOOL_DESCRIPTION} from "../agent-plugin-core/typescript/src/prompts.ts";

async function getUserId(): Promise<string> {
  if (process.env.MEM0_USER_ID) return process.env.MEM0_USER_ID;
  try {
    return userInfo().username;
  } catch {
  }
  return process.env.USER || process.env.USERNAME || "unknown";
}

function generateSessionId(): string {
  const ts = Math.floor(Date.now() / 1000);
  const rnd = randomBytes(3).toString("hex");
  return `ses_${ts}_${rnd}`;
}

/** Read & parse `~/.mem0/settings.json`, returning {} when missing/invalid. */
function loadSettings(): Record<string, unknown> {
  try {
    const settingsPath = join(homedir(), ".mem0", "settings.json");
    if (!existsSync(settingsPath)) return {};
    return JSON.parse(readFileSync(settingsPath, "utf8"));
  } catch {
  }
  return {};
}

function loadGlobalSearch(): boolean {
  return loadSettings().global_search === true;
}

/**
 * The user's persisted default memory scope (set via the `mem0-scope` skill).
 * Read fresh so a scope change takes effect on the next memory operation without
 * restarting OpenCode. Defaults to "project".
 */
function loadDefaultScope(): Scope {
  return resolveDefaultScope(loadSettings());
}

function resolveFilters(args: any, globalSearch: boolean, userId: string, appId: string): any {
  if (args.filters) {
    const existingFilters = args.filters;
    if (typeof existingFilters === "object" && existingFilters !== null) {
      const andClauses: any[] = existingFilters.AND;
      if (Array.isArray(andClauses)) {
        const hasUid = andClauses.some(
          (c: any) => c && typeof c === "object" && "user_id" in c,
        );
        const hasAid = andClauses.some(
          (c: any) => c && typeof c === "object" && "app_id" in c,
        );
        const hasAgentId = andClauses.some(
          (c: any) => c && typeof c === "object" && "agent_id" in c,
        );
        const newClauses = [...andClauses];
        if (args.agent_id || hasAgentId) {
          if (!hasAgentId) newClauses.push({ agent_id: args.agent_id });
        } else {
          if (!hasUid) newClauses.push({ user_id: args.user_id ?? userId });
        }
        if (!hasAid) newClauses.push({ app_id: args.app_id ?? appId });
        return { AND: newClauses };
      } else if (andClauses === undefined) {
        const hasUid = "user_id" in existingFilters;
        const hasAid = "app_id" in existingFilters;
        const hasAgentId = "agent_id" in existingFilters;
        if (!hasAid || (!hasUid && !hasAgentId)) {
          const existing = Object.entries(existingFilters).map(
            ([k, v]) => ({ [k]: v }),
          );
          if (args.agent_id || hasAgentId) {
            if (!hasAgentId) existing.push({ agent_id: args.agent_id });
          } else {
            if (!hasUid) existing.push({ user_id: args.user_id ?? userId });
          }
          if (!hasAid) existing.push({ app_id: args.app_id ?? appId });
          return { AND: existing };
        }
      }
    }
    return args.filters;
  }

  if (globalSearch) {
    return { OR: [{ user_id: "*" }] };
  }

  if (args.agent_id) {
    return {
      AND: [{ agent_id: args.agent_id }, { app_id: args.app_id ?? appId }],
    };
  }

  return {
    AND: [{ user_id: args.user_id ?? userId }, { app_id: args.app_id ?? appId }],
  };
}

function extractUserText(input: any, output: any): string {
  const parts: any[] = output?.parts;
  if (Array.isArray(parts)) {
    return parts
      .filter((p: any) => p.type === "text" && !p.synthetic)
      .map((p: any) => p.text ?? "")
      .join("\n");
  }
  const msg = output?.message ?? input?.message;
  if (typeof msg?.content === "string") return msg.content;
  if (typeof msg?.text === "string") return msg.text;
  return "";
}

interface SessionMemory {
  lifecycle: ReturnType<typeof createMemoryLifecycle>;
  context: string;
  assistant: { messageID: string; text: string };
}

const Mem0Plugin: Plugin = async (ctx) => {
  const {client} = ctx;

  const apiKey = resolveApiKey(process.env, process.env.HOME || process.env.USERPROFILE || homedir());

  if (!apiKey) {
    try {
      await client.app.log({
        body: {
          service: "mem0",
          level: "error",
          message:
            "MEM0_API_KEY environment variable not set. Get one at https://app.mem0.ai/dashboard/api-keys",
        },
      });
    } catch {
    }
    return {};
  }

  const mem0 = new MemoryClient({apiKey});
  const userId = await getUserId();
  const repo = resolveRepoContext(ctx.directory || process.cwd(), process.env.MEM0_APP_ID ?? "");
  const {appId, branch} = repo;
  const stats = {adds: 0, searches: 0, messages: 0};
  const sessionId = generateSessionId();
  const globalSearch = loadGlobalSearch();
  const lifecycle = createMemoryLifecycle();
  const sessions = new Map<string, SessionMemory>();
  const childSessions = new Set<string>();

  let sessionStopSent = false;
  const emitSessionStop = () => {
    if (sessionStopSent) return;
    sessionStopSent = true;
    captureEvent(
      "session_stop",
      {adds: stats.adds, searches: stats.searches, messages: stats.messages},
      apiKey,
      appId,
    );
  };
  const shutdown = async () => {
    await Promise.all([...sessions.keys()].map(endSession));
    emitSessionStop();
  };
  try {
    process.on("beforeExit", () => void shutdown());
  } catch {
  }

  // Register a `/mem0-<skill>` slash command per bundled skill. OpenCode's TUI
  // slash menu is populated from `config.command` entries (skills discovered via
  // `skills.paths` are available to the agent's skill tool but do NOT appear as
  // slash commands), so this is what makes `/mem0-scope` etc. typeable.
  function registerCommands(skillsDir: string, opencodeConfig: any) {
    for (const entry of readdirSync(skillsDir, {withFileTypes: true})) {
      if (!entry.isDirectory()) continue;
      const skillMd = resolve(skillsDir, entry.name, "SKILL.md");
      if (!existsSync(skillMd)) continue;

      let desc = `Mem0 ${entry.name} skill`;
      try {
        const content = readFileSync(skillMd, "utf8");
        const m = content.match(/^description:\s*(.+)$/m);
        if (m) desc = m[1].trim();
      } catch {
      }

      opencodeConfig.command ??= {};
      opencodeConfig.command[entry.name] = {
        template: `Load and execute the \`${entry.name}\` skill.

Use the mem0 memory tools (add_memory, search_memories, get_memories, get_memory, update_memory, delete_memory, delete_all_memories, delete_entities, list_entities, get_event_status) as instructed by the skill.

Identity context (resolved at plugin startup):
- user_id: ${userId}
- app_id: ${appId}
- session_id: ${sessionId}
- branch: ${branch || "unknown"}`,
        description: desc,
      };
    }
  }

  // Resolve read filters for the memory tools. Precedence: an explicit `scope`
  // arg wins; then explicit `filters`/`agent_id`; otherwise fall back to the
  // user's persisted default scope (read fresh so /mem0-scope applies at once).
  // A "project" default preserves the existing behavior, including global_search.
  function readScopeFilters(args: any, runId: string): any {
    if (args.scope) return scopeSearchFilters(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, runId, repo.projectIds);
    if (args.filters || args.agent_id) return resolveFilters(args, globalSearch, userId, appId);
    const ds = loadDefaultScope();
    return ds === "project" && (globalSearch || args.user_id || args.app_id)
      ? resolveFilters(args, globalSearch, userId, appId)
      : scopeSearchFilters(ds, userId, appId, runId, repo.projectIds);
  }

  return {
    "chat.message": chatMessageHook,
    "experimental.chat.messages.transform": chatMessagesTransformHook,
    "experimental.text.complete": textCompleteHook,
    "experimental.session.compacting": compactionHook,
    event: eventHook,
    dispose: shutdown,

    "shell.env": async (
      input: { cwd: string; sessionID?: string },
      output: { env: Record<string, string> },
    ) => {
      if (output?.env) {
        output.env.MEM0_USER_ID = userId;
        output.env.MEM0_APP_ID = appId;
        output.env.MEM0_SESSION_ID = input?.sessionID || sessionId;
        output.env.MEM0_BRANCH = branch;
        output.env.MEM0_GLOBAL_SEARCH = globalSearch ? "true" : "false";
      }
    },

    config: async (opencodeConfig: any) => {
      // Point OpenCode at the plugin's OWN skills directory via `skills.paths`
      const here = import.meta.filename;
      const skillsDir = [
        resolve(dirname(dirname(here)), "opencode-skills"),
        resolve(dirname(here), "opencode-skills"),
      ].find(existsSync);
      if (!skillsDir) return;

      opencodeConfig.skills ??= {};
      opencodeConfig.skills.paths ??= [];
      if (!opencodeConfig.skills.paths.includes(skillsDir)) {
        opencodeConfig.skills.paths.push(skillsDir);
      }

      // Register the /mem0-* slash commands (the TUI slash menu reads these from
      // config.command; skills.paths alone does not create slash commands).
      registerCommands(skillsDir, opencodeConfig);
    },

    tool: {
      add_memory: tool({
        description: "Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something. Set infer to false to store the memory verbatim without LLM fact extraction.",
        args: {
          text: tool.schema.string().describe("Memory text content"),
          user_id: tool.schema.string().optional().describe("User ID"),
          app_id: tool.schema.string().optional().describe("App/Project ID"),
          agent_id: tool.schema.string().optional().describe("Agent ID"),
          metadata: tool.schema.record(tool.schema.string(), tool.schema.any()).optional().describe("Metadata key-value pairs"),
          infer: tool.schema.boolean().optional().describe("Set to false to store memory verbatim without LLM fact extraction"),
          scope: tool.schema.string().optional().describe('Write scope: "project" (this repo, default), "session" (this run), or "global" (user-wide, all projects). Use "global" only when explicitly asked.')
        },
        async execute(args, context) {
          stats.adds++;
          captureEvent("tool_use", {tool: "add_memory"}, apiKey, appId);
          const runId = context?.sessionID || sessionId;
          const effScope: Scope = resolveToolScope(args.scope ? asScope(args.scope) : undefined, loadDefaultScope());
          const sp = scopeWriteParams(effScope, userId, appId, runId);
          const finalUserId = args.agent_id ? args.user_id : (args.user_id ?? sp.user_id);
          const finalAppId = args.app_id ?? sp.app_id;

          const meta = args.metadata ?? {};
          if (meta.confidence === undefined) meta.confidence = 0.7;
          if (!meta.source) meta.source = "opencode";
          if (!meta.type) meta.type = "task_learning";
          if (!meta.session_id) meta.session_id = runId;
          if (!meta.files) meta.files = ["*"];
          if (!meta.branch && branch) meta.branch = branch;

          let infer = args.infer;
          if (meta.confidence >= 1.0 && infer === undefined) {
            infer = false;
          }

          const res = await mem0.add(
            [{ role: "user", content: lifecycle.prepareUserText(args.text) }],
            {
              user_id: finalUserId,
              app_id: finalAppId,
              run_id: sp.run_id,
              agent_id: args.agent_id,
              metadata: meta,
              infer
            } as any
          );
          return JSON.stringify(res);
        }
      }),

      search_memories: tool({
        description: SEARCH_TOOL_DESCRIPTION,
        args: {
          query: tool.schema.string().describe(SEARCH_QUERY_DESCRIPTION),
          user_id: tool.schema.string().optional().describe("User ID"),
          app_id: tool.schema.string().optional().describe("App/Project ID"),
          agent_id: tool.schema.string().optional().describe("Agent ID"),
          filters: tool.schema.record(tool.schema.string(), tool.schema.any()).optional().describe("Key-value filters (e.g. metadata or user/app filters)"),
          limit: tool.schema.number().optional().describe("Maximum number of results to return (top_k)"),
          top_k: tool.schema.number().optional().describe("Maximum number of results to return (alternative parameter)"),
          scope: tool.schema.string().optional().describe('Search scope: "project" (this repo, default), "session" (this run only), or "global" (across ALL your projects). Only use "global" when the user explicitly asks to search across projects.'),
        },
        async execute(args, context) {
          stats.searches++;
          captureEvent("tool_use", {tool: "search_memories"}, apiKey, appId);
          const topK = args.limit ?? args.top_k ?? 10;
          const filters = readScopeFilters(args, context?.sessionID || sessionId);

          const res = await mem0.search(lifecycle.prepareUserText(args.query), {
            filters,
            topK,
          });
          return JSON.stringify(res);
        }
      }),

      get_memories: tool({
        description: "List or browse stored memories without a search query -- useful for auditing what is remembered or paging through everything in a scope. To find memories relevant to a question, use search_memories instead (it ranks by semantic relevance).",
        args: {
          user_id: tool.schema.string().optional().describe("User ID"),
          app_id: tool.schema.string().optional().describe("App/Project ID"),
          agent_id: tool.schema.string().optional().describe("Agent ID"),
          filters: tool.schema.record(tool.schema.string(), tool.schema.any()).optional().describe("Metadata/identity filters"),
          page: tool.schema.number().optional().describe("Page number"),
          page_size: tool.schema.number().optional().describe("Page size"),
          scope: tool.schema.string().optional().describe('Scope: "project" (default), "session", or "global" (across ALL your projects). Use "global" only when explicitly asked.'),
        },
        async execute(args, context) {
          captureEvent("tool_use", {tool: "get_memories"}, apiKey, appId);
          const filters = readScopeFilters(args, context?.sessionID || sessionId);

          const res = await mem0.getAll({
            page: args.page,
            pageSize: args.page_size,
            filters,
          });
          return JSON.stringify(res);
        }
      }),

      get_memory: tool({
        description: "Fetch one memory by its exact ID (e.g. an ID returned by search_memories or get_memories) to read its full content and metadata.",
        args: {
          id: tool.schema.string().describe("The ID of the memory to retrieve"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "get_memory"}, apiKey, appId);
          const res = await mem0.get(args.id);
          return JSON.stringify(res);
        }
      }),

      update_memory: tool({
        description: "Update an existing memory in place when a stored fact has changed -- requires the memory ID. Preserves the ID and history, so prefer this over deleting and re-adding.",
        args: {
          id: tool.schema.string().describe("The ID of the memory to update"),
          text: tool.schema.string().optional().describe("New text content for the memory"),
          metadata: tool.schema.record(tool.schema.string(), tool.schema.any()).optional().describe("New metadata key-value pairs"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "update_memory"}, apiKey, appId);
          const res = await mem0.update(args.id, {
            text:
              args.text === undefined
                ? undefined
                : lifecycle.prepareUserText(args.text),
            metadata: args.metadata,
          });
          return JSON.stringify(res);
        }
      }),

      delete_memory: tool({
        description: "Delete one or more memories by ID when they are wrong, obsolete, or the user asks to forget them. Irreversible -- only delete what is clearly no longer wanted.",
        args: {
          id: tool.schema.string().describe("The ID of the memory to delete"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "delete_memory"}, apiKey, appId);
          const res = await mem0.delete(args.id);
          return JSON.stringify(res);
        }
      }),

      delete_all_memories: tool({
        description: "Delete ALL memories in the given scope. Destructive and irreversible -- only use when the user explicitly asks to wipe their memory. Never call speculatively.",
        args: {
          user_id: tool.schema.string().optional().describe("User ID whose memories to delete"),
          app_id: tool.schema.string().optional().describe("App ID whose memories to delete"),
          agent_id: tool.schema.string().optional().describe("Agent ID whose memories to delete"),
          scope: tool.schema.string().optional().describe('Scope to delete: "project" (default), "session", or "global" (user-wide). Use "global" only when explicitly asked.'),
        },
        async execute(args, context) {
          captureEvent("tool_use", {tool: "delete_all_memories"}, apiKey, appId);
          const sp = args.scope ? scopeWriteParams(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, context?.sessionID || sessionId) : null;
          const res = await mem0.deleteAll({
            user_id: sp ? sp.user_id : (args.agent_id ? args.user_id : (args.user_id ?? userId)),
            app_id: sp ? sp.app_id : (args.app_id ?? appId),
            run_id: sp?.run_id,
            agent_id: args.agent_id,
          } as any);
          return JSON.stringify(res);
        }
      }),

      delete_entities: tool({
        description: "Delete entire user/agent/app/run entities and every memory attached to them. Destructive and irreversible -- only on explicit user request to remove a whole user, agent, or project.",
        args: {
          user_id: tool.schema.string().optional().describe("User ID of the entity to delete"),
          agent_id: tool.schema.string().optional().describe("Agent ID of the entity to delete"),
          app_id: tool.schema.string().optional().describe("App/Project ID of the entity to delete"),
          run_id: tool.schema.string().optional().describe("Run ID of the entity to delete"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "delete_entities"}, apiKey, appId);
          const res = await mem0.deleteUsers({
            userId: args.user_id,
            agentId: args.agent_id,
            appId: args.app_id,
            runId: args.run_id,
          });
          return JSON.stringify(res);
        }
      }),

      list_entities: tool({
        description: "List the user/agent/app/run entities that have memories. Use to discover which scopes exist before searching, listing, or deleting within a specific one.",
        args: {
          page: tool.schema.number().optional().describe("Page number"),
          page_size: tool.schema.number().optional().describe("Page size"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "list_entities"}, apiKey, appId);
          const res = await mem0.users({
            page: args.page,
            pageSize: args.page_size,
          });
          return JSON.stringify(res);
        }
      }),

      get_event_status: tool({
        description: "Check whether an asynchronous memory write (add/update/delete) finished, using the event_id that call returned. Poll this when you need to confirm a write was persisted before relying on it.",
        args: {
          event_id: tool.schema.string().describe("The ID of the event/async operation to check"),
        },
        async execute(args) {
          captureEvent("tool_use", {tool: "get_event_status"}, apiKey, appId);
          const response = await mem0.client.get(`/v1/event/${args.event_id}/`);
          return JSON.stringify(response.data);
        }
      }),
    },
  };

  async function send(runId: string, messages: ConversationMessage[], reason: string) {
    try {
      await mem0.add(messages, repoCaptureOptions(repo, userId, runId, "opencode") as any);
      stats.adds++;
      captureEvent("flush", {reason, message_count: messages.length, success: true}, apiKey, appId);
    } catch (err: any) {
      captureEvent("flush", {reason, message_count: messages.length, success: false}, apiKey, appId);
      try {
        await client.app.log({body: {service: "mem0", level: "error", message: `Memory capture failed: ${err?.message}`}});
      } catch {
      }
    }
  }

  function sender(runId: string) {
    return (messages: ConversationMessage[], reason: string) => send(runId, messages, reason);
  }

  function recordAssistant(state: SessionMemory) {
    state.lifecycle.recordAssistantResponse(state.assistant.text);
    state.assistant = {messageID: "", text: ""};
  }

  async function endSession(runId: string) {
    const state = sessions.get(runId);
    if (!state) return;
    sessions.delete(runId);
    recordAssistant(state);
    await state.lifecycle.end("session-end", sender(runId));
  }

  async function chatMessageHook(input: any, output: any) {
    const runId: string = input?.sessionID ?? "";
    if (!runId || childSessions.has(runId)) return;
    let state = sessions.get(runId);
    if (!state) {
      const sessionLifecycle = createMemoryLifecycle();
      sessionLifecycle.beginSession();
      state = {lifecycle: sessionLifecycle, context: "", assistant: {messageID: "", text: ""}};
      sessions.set(runId, state);
      captureEvent("session_start", {}, apiKey, appId);
    }
    const userText = extractUserText(input, output);
    state.lifecycle.recordUserPrompt(userText);
    stats.messages++;
    state.context = await state.lifecycle.recall(userText, true, async (query) => {
      stats.searches++;
      return mem0.search(query, {
        filters: scopeSearchFilters("project", userId, appId, runId, repo.projectIds),
        topK: RECALL_TOP_K,
        rerank: false,
        latestOnly: true,
      } as any);
    });
    captureEvent("user_prompt", {}, apiKey, appId);
  }

  async function chatMessagesTransformHook(_input: any, output: { messages: { info: any; parts: any[] }[] }) {
    const firstUser = output?.messages?.find((m) => m.info.role === "user");
    const context = firstUser ? sessions.get(firstUser.info.sessionID)?.context : "";
    if (!context || !firstUser?.parts.length) return;
    if (firstUser.parts.some((p: any) => p.type === "text" && p.text === context)) return;
    firstUser.parts.unshift({...firstUser.parts[0], type: "text", text: context});
  }

  async function textCompleteHook(input: { sessionID: string; messageID: string }, output: { text: string }) {
    const state = sessions.get(input?.sessionID);
    if (!state || !output?.text) return;
    state.assistant = state.assistant.messageID === input.messageID
      ? {messageID: input.messageID, text: `${state.assistant.text}\n${output.text}`}
      : {messageID: input.messageID, text: output.text};
  }

  async function onIdle(runId: string) {
    const state = sessions.get(runId);
    if (!state) return;
    recordAssistant(state);
    await state.lifecycle.afterResponse(sender(runId));
  }

  async function eventHook({event}: { event: any }) {
    const info = event?.properties?.info;
    if (event?.type === "session.created" && info?.parentID) childSessions.add(info.id);
    else if (event?.type === "session.idle") await onIdle(event.properties?.sessionID);
    else if (event?.type === "session.deleted" && info?.id) {
      childSessions.delete(info.id);
      await endSession(info.id);
    }
  }

  async function compactionHook(input: { sessionID?: string }, _output: { context: string[]; prompt?: string }) {
    const runId = input?.sessionID ?? "";
    captureEvent(
      "pre_compact",
      {adds: stats.adds, searches: stats.searches, messages: stats.messages},
      apiKey,
      appId,
    );
    await sessions.get(runId)?.lifecycle.flush("pre-compact", sender(runId));
  }
};

export default Mem0Plugin;
