import { resolveToolScope } from "../agent-plugin-core/typescript/src/scoping.ts";
// Mem0 memory plugin for OpenCode: captures and recalls memories across sessions
// (add / search / manage) via the Mem0 platform, wired through OpenCode plugin hooks.
// Memory operations are exposed as native OpenCode tools backed by the mem0ai SDK
// (no MCP server required).
import type {Plugin} from "@opencode-ai/plugin";
import {tool} from "@opencode-ai/plugin";
import {MemoryClient} from "mem0ai";
import {userInfo} from "os";
import {basename, resolve, dirname} from "path";
import {randomBytes} from "crypto";
import {existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync} from "fs";
import {homedir} from "os";
import {join} from "path";
import {createHash} from "crypto";
import {captureEvent} from "./telemetry";
import {asScope, scopeSearchFilters, scopeWriteParams, resolveDefaultScope, SCOPE_GUIDANCE, type Scope} from "./scope";
import {parseProjectFromRemote} from "./project";
import {resolveApiKey} from "./api-key";
import {createMemoryLifecycle} from "../agent-plugin-core/typescript/src/lifecycle.ts";
import {SEARCH_QUERY_DESCRIPTION, SEARCH_TOOL_DESCRIPTION} from "../agent-plugin-core/typescript/src/prompts.ts";

async function getUserId(): Promise<string> {
  if (process.env.MEM0_USER_ID) return process.env.MEM0_USER_ID;
  try {
    return userInfo().username;
  } catch {
  }
  return process.env.USER || process.env.USERNAME || "unknown";
}

async function getProjectId($: any): Promise<string> {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
  // Prefer the git remote's owner/repo — stable across clones, worktrees, and
  // sub-directories (handles https + ssh, incl. custom host aliases).
  try {
    const r = await $`git remote get-url origin`.quiet();
    const project = parseProjectFromRemote(r.stdout.toString());
    if (project) return project;
  } catch {
  }
  // No usable remote: use the git repo ROOT dir name, not cwd (which may be a
  // sub-directory, or your home dir if OpenCode was launched outside a repo).
  try {
    const r = await $`git rev-parse --show-toplevel`.quiet();
    const top = r.stdout.toString().trim();
    if (top) return basename(top);
  } catch {
  }
  return basename(process.cwd());
}

async function getBranch($: any): Promise<string> {
  try {
    const r = await $`git branch --show-current`.quiet();
    return r.stdout.toString().trim() || "main";
  } catch {
  }
  return "main";
}

function extractMemories(res: any): Array<{ memory: string; id: string }> {
  const arr = res?.results ?? res;
  if (!Array.isArray(arr)) return [];
  return arr.map((m: any) => ({memory: m.memory ?? "", id: m.id ?? ""}));
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

const CODING_CATEGORIES = [
  "architecture_decisions", "api_design", "data_models", "algorithms",
  "dependencies", "environment_setup", "testing_strategy", "debugging_notes",
  "performance", "security", "deployment", "code_conventions",
  "error_handling", "refactoring_history", "integrations", "onboarding",
  "project_meta",
];

function categoriesFingerprint(): string {
  const sorted = [...CODING_CATEGORIES].sort();
  return createHash("sha256").update(sorted.join("\n")).digest("hex").slice(0, 16);
}

function apiKeyFingerprint(apiKey: string): string {
  return createHash("sha256").update(apiKey).digest("hex").slice(0, 16);
}

async function autoSetupCategories(mem0: MemoryClient, apiKey: string): Promise<void> {
  const stateDir = join(homedir(), ".mem0");
  const stateFile = join(stateDir, "categories_setup.json");
  const keyFp = apiKeyFingerprint(apiKey);
  const catFp = categoriesFingerprint();

  let state: Record<string, string> = {};
  try {
    if (existsSync(stateFile)) {
      state = JSON.parse(readFileSync(stateFile, "utf8"));
    }
  } catch {}

  if (state[keyFp] === catFp) return;

  try {
    const project = await mem0.getProject({fields: ["customCategories"]});
    const existing: string[] = (project as any)?.custom_categories ?? (project as any)?.customCategories ?? [];
    const sortedExisting = [...existing].sort();
    const sortedTarget = [...CODING_CATEGORIES].sort();
    if (JSON.stringify(sortedExisting) === JSON.stringify(sortedTarget)) {
      state[keyFp] = catFp;
      mkdirSync(stateDir, {recursive: true});
      writeFileSync(stateFile, JSON.stringify(state, null, 2) + "\n");
      return;
    }

    await mem0.updateProject({customCategories: CODING_CATEGORIES as any});

    state[keyFp] = catFp;
    mkdirSync(stateDir, {recursive: true});
    writeFileSync(stateFile, JSON.stringify(state, null, 2) + "\n");
  } catch {
  }
}

const NUDGE_RE =
  /\b(remember\s+(this|that)|memorize|save\s+this|note\s+(this|that)|don'?t\s+forget|always\s+remember|never\s+forget|keep\s+(this|that)\s+in\s+(mind|memory)|store\s+(this|that))\b/i;

const RESUME_RE =
  /where\s+(did\s+)?(we|I)\s+(leave|left)\s+off|continue\s+(from\s+)?(where|last)|what\s+were\s+we\s+(working|doing)|pick\s+up\s+where|resume\s+(from\s+|where\s+)|what.s\s+the\s+(current|latest)\s+(state|status)|catch\s+me\s+up|where\s+are\s+we/i;

const ERROR_STRONG_RE =
  /Traceback \(most recent call last\)|panic: |FATAL:|error\[E\d+\]/;
const ERROR_MULTI_RE = /(Error:|Exception:)/g;
const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit", "write", "edit", "multiEdit"]);

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

/**
 * Skill directory discovery for the V2 `skill.transform` registration path
 * (the V1 `config` hook keeps its own inline copy): the plugin ships its
 * skills next to the bundle.
 */
function discoverSkillsDir(): string | undefined {
  const here = import.meta.filename;
  return [
    resolve(dirname(dirname(here)), "opencode-skills"),
    resolve(dirname(here), "opencode-skills"),
  ].find(existsSync);
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

const Mem0Plugin: Plugin = async (ctx) => {
  const {$, client} = ctx;

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
  const appId = await getProjectId($);
  const branch = await getBranch($);
  const stats = {adds: 0, searches: 0, messages: 0};
  const sessionId = generateSessionId();
  const globalSearch = loadGlobalSearch();
  const lifecycle = createMemoryLifecycle();
  lifecycle.beginSession();

  let initialized = false;
  let memoryCount = 0;
  let msgCount = 0;

  const systemContext: string[] = [];

  // Emit a session_stop telemetry event once when the process winds down.
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
  try {
    process.on("beforeExit", emitSessionStop);
  } catch {
  }

  // Auto-configure coding categories in background (idempotent, never blocks)
  Promise.resolve().then(() => autoSetupCategories(mem0, apiKey)).catch(() => {
  });

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
- branch: ${branch}`,
        description: desc,
      };
    }
  }

  // Resolve read filters for the memory tools. Precedence: an explicit `scope`
  // arg wins; then explicit `filters`/`agent_id`; otherwise fall back to the
  // user's persisted default scope (read fresh so /mem0-scope applies at once).
  // A "project" default preserves the existing behavior, including global_search.
  function readScopeFilters(args: any): any {
    if (args.scope) return scopeSearchFilters(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, sessionId);
    if (args.filters || args.agent_id) return resolveFilters(args, globalSearch, userId, appId);
    const ds = loadDefaultScope();
    return ds === "project"
      ? resolveFilters(args, globalSearch, userId, appId)
      : scopeSearchFilters(ds, userId, appId, sessionId);
  }

  return {
    "chat.message": chatMessageHook,
    "experimental.chat.messages.transform": chatMessagesTransformHook,
    "tool.execute.before": toolExecuteBeforeHook,
    "tool.execute.after": toolExecuteAfterHook,
    "experimental.session.compacting": compactionHook,

    "shell.env": async (
      _input: { cwd: string; sessionID?: string },
      output: { env: Record<string, string> },
    ) => {
      if (output?.env) {
        output.env.MEM0_USER_ID = userId;
        output.env.MEM0_APP_ID = appId;
        output.env.MEM0_SESSION_ID = sessionId;
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
        async execute(args) {
          stats.adds++;
          captureEvent("tool_use", {tool: "add_memory"}, apiKey, appId);
          const effScope: Scope = resolveToolScope(args.scope ? asScope(args.scope) : undefined, loadDefaultScope());
          const sp = scopeWriteParams(effScope, userId, appId, sessionId);
          const finalUserId = args.agent_id ? args.user_id : (args.user_id ?? sp.user_id);
          const finalAppId = args.app_id ?? sp.app_id;

          const meta = args.metadata ?? {};
          if (meta.confidence === undefined) meta.confidence = 0.7;
          if (!meta.source) meta.source = "opencode";
          if (!meta.type) meta.type = "task_learning";
          if (!meta.session_id) meta.session_id = sessionId;
          if (!meta.files) meta.files = ["*"];
          if (!meta.branch) meta.branch = branch;

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
        async execute(args) {
          stats.searches++;
          captureEvent("tool_use", {tool: "search_memories"}, apiKey, appId);
          const topK = args.limit ?? args.top_k ?? 10;
          const filters = readScopeFilters(args);

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
        async execute(args) {
          captureEvent("tool_use", {tool: "get_memories"}, apiKey, appId);
          const filters = readScopeFilters(args);

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
        async execute(args) {
          captureEvent("tool_use", {tool: "delete_all_memories"}, apiKey, appId);
          const sp = args.scope ? scopeWriteParams(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, sessionId) : null;
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

  async function chatMessageHook(input: any, output: any) {
    const userText = extractUserText(input, output);
    if (!userText || userText.length < 10) return;

    const safeText = lifecycle.prepareUserText(userText);
    msgCount++;
    stats.messages++;

    if (!initialized) {
      initialized = true;

      const searchFilters = globalSearch
        ? {OR: [{user_id: "*"}]}
        : {AND: [{user_id: userId}, {app_id: appId}]};

      try {
        const all = await mem0.getAll({
          filters: searchFilters,
          page: 1,
          pageSize: 1,
        });
        const a: any = all;
        memoryCount =
          typeof a?.count === "number"
            ? a.count
            : Array.isArray(a)
              ? a.length
              : Array.isArray(a?.results)
                ? a.results.length
                : 0;

        if (globalSearch) {
          systemContext.push(
            `Global search is ON — searches return all memories across all users and projects. Writes still use user_id="${userId}", app_id="${appId}".`,
          );
        } else {
          systemContext.push(
            `Always include user_id="${userId}" and app_id="${appId}" in every search_memories filter and add_memory call.`,
          );
        }

        if (memoryCount === 0) {
          systemContext.push(
            "New project with 0 memories. Capture decisions, conventions, and learnings as you work via the add_memory tool or the remember skill.",
          );
        }

        if (memoryCount > 0) {
          try {
            const res = await mem0.search(
              "recent session state decisions and learnings",
              {
                filters: searchFilters,
                topK: 5,
              },
            );
            stats.searches++;
            const memories = extractMemories(res);
            if (memories.length > 0) {
              const memLines = memories
                .map((m) => `- ${m.memory}`)
                .join("\n");
              systemContext.push(`Prior context from mem0:\n${memLines}`);
            }
          } catch {
          }
        }

        systemContext.push(SCOPE_GUIDANCE);
        const activeScope = loadDefaultScope();
        if (activeScope !== "project") {
          systemContext.push(
            `Active default memory scope is "${activeScope}" (set via /mem0-scope). Memory tools use this when no explicit scope is given: "session" limits to this run (run_id="${sessionId}"); "global" spans all your projects (app_id="*"). Pass an explicit scope to override per call. delete_all_memories still requires an explicit scope="global" to delete user-wide.`,
          );
        }
      } catch (err: any) {
        try {
          await client.app.log({
            body: {
              service: "mem0",
              level: "error",
              message: `Session init error: ${err?.message}`,
            },
          });
        } catch {
        }
      }

      captureEvent("session_start", {memory_count: memoryCount}, apiKey, appId);

    }

    const hasRemember = NUDGE_RE.test(safeText);
    if (hasRemember) {
      systemContext.push(
        "[MEMORY TRIGGER] User asked to remember something. Call add_memory with the user's statement, confidence=1.0, infer=false.",
      );
    }

    const hasResume = RESUME_RE.test(safeText);
    if (hasResume) {
      try {
        const resumeFilters = globalSearch
          ? {OR: [{user_id: "*"}]}
          : {
            AND: [
              {user_id: userId},
              {app_id: appId},
            ],
          };
        const [stateRes, decisionsRes] = await Promise.all([
          mem0.search("session state current task", {
            filters: resumeFilters,
            topK: 3,
          }),
          mem0.search("recent decisions and learnings", {
            filters: resumeFilters,
            topK: 3,
          }),
        ]);
        stats.searches += 2;
        const all = [
          ...extractMemories(stateRes),
          ...extractMemories(decisionsRes),
        ];
        const seen = new Set<string>();
        const unique = all.filter((m) => {
          if (seen.has(m.id)) return false;
          seen.add(m.id);
          return true;
        });
        if (unique.length > 0) {
          const memLines = unique.map((m) => `- ${m.memory}`).join("\n");
          systemContext.push(
            `Session resume context:\n${memLines}\n\nThese memories provide context for resuming work.`,
          );
        }
      } catch {
      }
    }

    if (!hasResume && memoryCount > 0) {
      try {
        const msgFilters = globalSearch
          ? {OR: [{user_id: "*"}]}
          : {AND: [{user_id: userId}, {app_id: appId}]};
        const res = await mem0.search(safeText, {
          filters: msgFilters,
          topK: 5,
        });
        stats.searches++;
        const memories = extractMemories(res);
        if (memories.length > 0) {
          const memLines = memories.map((m) => `- ${m.memory}`).join("\n");
          systemContext.push(`Relevant memories:\n${memLines}`);
        }
      } catch {
      }
    }

    if (msgCount % 3 === 0) {
      Promise.resolve().then(async () => {
        try {
          await mem0.add([{role: "user", content: safeText}], {
            user_id: userId,
            app_id: appId,
            metadata: {
              type: "auto_capture",
              source: "opencode",
              confidence: 0.7,
              session_id: sessionId,
              branch,
            },
            infer: true,
          } as any);
          stats.adds++;
        } catch {
        }
      });
    }

    if (msgCount % 5 === 0 && stats.adds < Math.floor(msgCount / 3)) {
      systemContext.push(
        "After responding, store any new decisions, learnings, or preferences from this exchange via add_memory. Keep it to 1 sentence per memory.",
      );
    }

    captureEvent(
      "user_prompt",
      {remember_detected: hasRemember, resume_detected: hasResume},
      apiKey,
      appId,
    );
  }

  async function toolExecuteBeforeHook(input: any, output: any) {
    const toolName: string = input?.tool ?? "";

    if (WRITE_TOOLS.has(toolName)) {
      const fp = String(
        output?.args?.file_path ?? output?.args?.filePath ?? "",
      );
      if (/MEMORY\.md|\.claude\/memory/i.test(fp)) {
        throw new Error(
          "Use the add_memory tool instead of writing to MEMORY.md",
        );
      }
    }
  }

  async function chatMessagesTransformHook(_input: any, output: { messages: { info: any; parts: any[] }[] }) {
    if (systemContext.length === 0 || !output?.messages?.length) return;

    const firstUser = output.messages.find(
      (m) => m.info.role === "user",
    );
    if (!firstUser || !firstUser.parts.length) return;

    const marker = "## Mem0 Memory Context";
    if (firstUser.parts.some((p: any) => p.type === "text" && p.text?.includes(marker))) return;

    const block = `${marker}\n\n${systemContext.join("\n\n")}`;
    const ref = firstUser.parts[0];
    firstUser.parts.unshift({...ref, type: "text", text: block});
  }

  async function toolExecuteAfterHook(input: any, _output: any) {
    const toolName: string = input?.tool ?? "";
    const toolOutput: string = input?.output ?? _output?.output ?? "";

    if (toolName === "bash" && toolOutput.length >= 50) {
      const command: string = input?.args?.command ?? "";
      if (/git\s+(commit|merge|rebase)/.test(command)) return;

      const hasStrongError = ERROR_STRONG_RE.test(toolOutput);
      const multiErrors = (toolOutput.match(ERROR_MULTI_RE) ?? []).length;
      if (!hasStrongError && multiErrors < 2) return;

      try {
        const errorLine =
          toolOutput
            .split("\n")
            .find((l: string) =>
              /Error:|Exception:|panic:|FAIL:|fatal:/i.test(l),
            )
            ?.replace(/^\s+/, "")
            .slice(0, 120) ?? "";

        const traceFiles = [
          ...new Set(
            toolOutput.match(
              /[a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh)(:\d+)?/g,
            ) ?? [],
          ),
        ].slice(0, 5);

        const errorQuery = errorLine.slice(0, 80);
        if (errorQuery.length < 10) return;

        captureEvent("bash_error", {error_detected: true}, apiKey, appId);

        const errorFilters = globalSearch
          ? {OR: [{user_id: "*"}]}
          : {
            AND: [
              {user_id: userId},
              {app_id: appId},
            ],
          };
        const res = await mem0.search(`error: ${errorQuery}`, {
          filters: errorFilters,
          topK: 6,
        });
        stats.searches++;
        const unique = extractMemories(res);

        let ctx = `Error detected: \`${command.slice(0, 100)}\` produced:\n> ${errorLine}`;
        if (traceFiles.length > 0) {
          ctx += `\nFiles in stack trace: ${traceFiles.join(", ")}`;
        }
        if (unique.length > 0) {
          const lines = unique.map((m) => `- ${m.memory}`).join("\n");
          ctx += `\nPrior error memories:\n${lines}`;
        }
        ctx +=
          "\nStore resolved errors as anti_pattern or bug_fix memories for future reference.";
        systemContext.push(ctx);
      } catch {
      }
    }
  }

  async function compactionHook(input: { sessionID?: string }, output: { context: string[]; prompt?: string }) {
    try {
      const compactSessionId = input?.sessionID ?? sessionId;
      captureEvent(
        "pre_compact",
        {adds: stats.adds, searches: stats.searches, messages: stats.messages},
        apiKey,
        appId,
      );
      const summaryContent = `Session compacting. Project: ${appId}. Branch: ${branch}. Session: ${compactSessionId}. Stats: ${stats.adds} memories stored, ${stats.searches} searches, ${stats.messages} messages.`;
      Promise.resolve().then(async () => {
        try {
          await mem0.add([{role: "user", content: summaryContent}], {
            user_id: userId,
            app_id: appId,
            metadata: {
              type: "session_state",
              source: "pre-compaction",
              session_id: compactSessionId,
              branch,
            },
            infer: true,
          } as any);
        } catch {
        }
      });

      const compactFilters = globalSearch
        ? {OR: [{user_id: "*"}]}
        : {AND: [{user_id: userId}, {app_id: appId}]};
      const res = await mem0.search("session state decisions learnings", {
        filters: compactFilters,
        topK: 10,
      });
      const memories = extractMemories(res);
      if (memories.length > 0 && output?.context) {
        const lines = memories.map((m) => `- ${m.memory}`).join("\n");
        output.context.push(
          `## Mem0 Memories (preserve across compaction)\n\n${lines}\n\nIMPORTANT: After compaction, store any key decisions or learnings using the add_memory tool.`,
        );
      }
    } catch {
    }
  }
};

// ---------------------------------------------------------------------------
// OpenCode V2 plugin (issue #7602)
//
// OpenCode V2's loader only accepts a default export shaped { id, effect | setup }
// (see opencode packages/core/src/plugin/module.ts — the PluginModule schema whose
// decode error is "Plugin must export a default definition with an id and an
// effect or setup function"). A bare async function default — the V1 contract —
// fails that decode with SchemaError(Expected object at ["default"]) and the
// module is dropped SILENTLY (exit 0, empty `plugin list`, one WARN in the log).
//
// The V2 entrypoint below re-exposes the same memory behavior through the V2
// registration APIs. V1 hosts keep working through the `server` key of the
// dual-shape default export (the shape recommended by OpenCode's V1->V2
// migration guide; V1 hosts need >= 1.18.29 for object entrypoints).
// ---------------------------------------------------------------------------

/**
 * Minimal structural types for the V2 SDK surface used below. They mirror
 * `@opencode/plugin` (npm, 2.x) so no runtime dependency on the V2 SDK is
 * needed — the loader only checks these shapes structurally.
 */
interface V2Registration {
  dispose: () => Promise<void>;
}

type V2HookRegistrar<Spec extends Record<string, any>> = <K extends keyof Spec>(
  name: K,
  callback: (input: Spec[K]) => Promise<void> | void,
) => Promise<V2Registration>;

/** opencode V2 `ctx.session.hook` payloads (packages/plugin/src/promise/session.ts). */
interface V2SessionHooks {
  prompt: {sessionID: string; messageID: string; prompt: {text?: string}};
  context: {sessionID: string; system: Array<{type: "text"; text: string}>};
  compaction: {sessionID: string; system: Array<{type: "text"; text: string}>};
}

/** opencode V2 `ctx.tool.hook` payloads (packages/plugin/src/promise/tool.ts). */
interface V2ToolHooks {
  "execute.before": {tool: string; input: unknown};
  "execute.after": {tool: string; input: unknown; status?: string; result?: {content?: unknown; output?: unknown}};
}

/** opencode V2 `ctx.shell.hook` payloads (packages/plugin/src/promise/shell.ts). */
interface V2ShellHooks {
  "create.before": {command: string; env: Record<string, string | undefined>};
}

/** Structural stand-in for the V2 plugin Context (packages/plugin/src/promise/plugin.ts). */
interface V2Context {
  app: {name: string; version: string; channel: string};
  session: {
    hook: V2HookRegistrar<V2SessionHooks>;
    prompt: (input: Record<string, unknown>) => Promise<unknown>;
  };
  tool: {
    hook: V2HookRegistrar<V2ToolHooks>;
    transform: (cb: (editor: {add: (tool: any) => void}) => void) => Promise<V2Registration>;
  };
  shell: {hook: V2HookRegistrar<V2ShellHooks>};
  skill: {transform: (cb: (editor: {add: (skill: any) => void}) => void) => Promise<V2Registration>};
  command: {transform: (cb: (editor: {add: (cmd: any) => void}) => void) => Promise<V2Registration>};
}

/** V2 tool definition (Tool.Info from packages/schema/src/tool.ts). */
interface V2Tool {
  name: string;
  description: string;
  input: Record<string, unknown>;
  execute: (args: any, context: any) => Promise<{content: string}>;
}

/** V2 default-export module shape accepted by the V2 loader's `server` key path. */
export interface Mem0PluginModule {
  id: string;
  setup: (ctx: V2Context) => Promise<void>;
  server: Plugin;
}

function v2Log(level: "error" | "warn", message: string): void {
  // V2 plugin contexts expose no client logging API; stderr is the honest channel.
  console.error(`[mem0] ${level}: ${message}`);
}

/** V1 hooks ran shell commands through Bun's `$`; V2 gets a plain exec-based helper. */
async function gitOut(args: string[]): Promise<string> {
  const {execFile} = await import("child_process");
  return new Promise((resolvePromise, reject) => {
    execFile("git", args, {maxBuffer: 1024 * 1024}, (err, stdout) => {
      if (err) reject(err);
      else resolvePromise(stdout.toString());
    });
  });
}

async function getProjectIdV2(): Promise<string> {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
  try {
    const project = parseProjectFromRemote(await gitOut(["remote", "get-url", "origin"]));
    if (project) return project;
  } catch {
  }
  try {
    const top = (await gitOut(["rev-parse", "--show-toplevel"])).trim();
    if (top) return basename(top);
  } catch {
  }
  return basename(process.cwd());
}

async function getBranchV2(): Promise<string> {
  try {
    return (await gitOut(["branch", "--show-current"])).trim() || "main";
  } catch {
  }
  return "main";
}

/** The 10 memory tools in the V2 Tool.Info shape (plain JSON Schema input). */
function buildV2Tools(deps: {
  mem0: MemoryClient;
  userId: string;
  appId: string;
  branch: string;
  sessionId: string;
  globalSearch: boolean;
  lifecycle: ReturnType<typeof createMemoryLifecycle>;
  readScopeFilters: (args: any) => any;
  apiKey: string;
  stats: {adds: number; searches: number; messages: number};
}): V2Tool[] {
  const {mem0, userId, appId, branch, sessionId, globalSearch, lifecycle, readScopeFilters, apiKey, stats} = deps;
  const stringSchema = {type: "string"} as const;
  const optional = (description: string) => ({type: "string", description});
  const objectSchema = (properties: Record<string, unknown>, required: string[]) => ({
    type: "object",
    properties,
    required,
    additionalProperties: false,
  });

  return [
    {
      name: "add_memory",
      description: "Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something. Set infer to false to store the memory verbatim without LLM fact extraction.",
      input: objectSchema({
        text: {...stringSchema, description: "Memory text content"},
        user_id: optional("User ID"),
        app_id: optional("App/Project ID"),
        agent_id: optional("Agent ID"),
        metadata: {type: "object", additionalProperties: true, description: "Metadata key-value pairs"},
        infer: {type: "boolean", description: "Set to false to store memory verbatim without LLM fact extraction"},
        scope: optional('Write scope: "project" (this repo, default), "session" (this run), or "global" (user-wide, all projects). Use "global" only when explicitly asked.'),
      }, ["text"]),
      async execute(args) {
        stats.adds++;
        captureEvent("tool_use", {tool: "add_memory"}, apiKey, appId);
        const effScope: Scope = resolveToolScope(args.scope ? asScope(args.scope) : undefined, loadDefaultScope());
        const sp = scopeWriteParams(effScope, userId, appId, sessionId);
        const finalUserId = args.agent_id ? args.user_id : (args.user_id ?? sp.user_id);
        const finalAppId = args.app_id ?? sp.app_id;

        const meta = args.metadata ?? {};
        if (meta.confidence === undefined) meta.confidence = 0.7;
        if (!meta.source) meta.source = "opencode";
        if (!meta.type) meta.type = "task_learning";
        if (!meta.session_id) meta.session_id = sessionId;
        if (!meta.files) meta.files = ["*"];
        if (!meta.branch) meta.branch = branch;

        let infer = args.infer;
        if (meta.confidence >= 1.0 && infer === undefined) {
          infer = false;
        }

        const res = await mem0.add(
          [{role: "user", content: lifecycle.prepareUserText(args.text)}],
          {
            user_id: finalUserId,
            app_id: finalAppId,
            run_id: sp.run_id,
            agent_id: args.agent_id,
            metadata: meta,
            infer,
          } as any,
        );
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "search_memories",
      description: SEARCH_TOOL_DESCRIPTION,
      input: objectSchema({
        query: {...stringSchema, description: SEARCH_QUERY_DESCRIPTION},
        user_id: optional("User ID"),
        app_id: optional("App/Project ID"),
        agent_id: optional("Agent ID"),
        filters: {type: "object", additionalProperties: true, description: "Key-value filters (e.g. metadata or user/app filters)"},
        limit: {type: "number", description: "Maximum number of results to return (top_k)"},
        top_k: {type: "number", description: "Maximum number of results to return (alternative parameter)"},
        scope: optional('Search scope: "project" (this repo, default), "session" (this run only), or "global" (across ALL your projects). Only use "global" when the user explicitly asks to search across projects.'),
      }, ["query"]),
      async execute(args) {
        stats.searches++;
        captureEvent("tool_use", {tool: "search_memories"}, apiKey, appId);
        const topK = args.limit ?? args.top_k ?? 10;
        const filters = readScopeFilters(args);
        const res = await mem0.search(lifecycle.prepareUserText(args.query), {filters, topK});
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "get_memories",
      description: "List or browse stored memories without a search query -- useful for auditing what is remembered or paging through everything in a scope. To find memories relevant to a question, use search_memories instead (it ranks by semantic relevance).",
      input: objectSchema({
        user_id: optional("User ID"),
        app_id: optional("App/Project ID"),
        agent_id: optional("Agent ID"),
        filters: {type: "object", additionalProperties: true, description: "Metadata/identity filters"},
        page: {type: "number", description: "Page number"},
        page_size: {type: "number", description: "Page size"},
        scope: optional('Scope: "project" (default), "session", or "global" (across ALL your projects). Use "global" only when explicitly asked.'),
      }, []),
      async execute(args) {
        captureEvent("tool_use", {tool: "get_memories"}, apiKey, appId);
        const filters = readScopeFilters(args);
        const res = await mem0.getAll({page: args.page, pageSize: args.page_size, filters});
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "get_memory",
      description: "Fetch one memory by its exact ID (e.g. an ID returned by search_memories or get_memories) to read its full content and metadata.",
      input: objectSchema({
        id: {...stringSchema, description: "The ID of the memory to retrieve"},
      }, ["id"]),
      async execute(args) {
        captureEvent("tool_use", {tool: "get_memory"}, apiKey, appId);
        const res = await mem0.get(args.id);
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "update_memory",
      description: "Update an existing memory in place when a stored fact has changed -- requires the memory ID. Preserves the ID and history, so prefer this over deleting and re-adding.",
      input: objectSchema({
        id: {...stringSchema, description: "The ID of the memory to update"},
        text: {type: "string", description: "New text content for the memory"},
        metadata: {type: "object", additionalProperties: true, description: "New metadata key-value pairs"},
      }, ["id"]),
      async execute(args) {
        captureEvent("tool_use", {tool: "update_memory"}, apiKey, appId);
        const res = await mem0.update(args.id, {
          text: args.text === undefined ? undefined : lifecycle.prepareUserText(args.text),
          metadata: args.metadata,
        });
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "delete_memory",
      description: "Delete one or more memories by ID when they are wrong, obsolete, or the user asks to forget them. Irreversible -- only delete what is clearly no longer wanted.",
      input: objectSchema({
        id: {...stringSchema, description: "The ID of the memory to delete"},
      }, ["id"]),
      async execute(args) {
        captureEvent("tool_use", {tool: "delete_memory"}, apiKey, appId);
        const res = await mem0.delete(args.id);
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "delete_all_memories",
      description: "Delete ALL memories in the given scope. Destructive and irreversible -- only use when the user explicitly asks to wipe their memory. Never call speculatively.",
      input: objectSchema({
        user_id: optional("User ID whose memories to delete"),
        app_id: optional("App ID whose memories to delete"),
        agent_id: optional("Agent ID whose memories to delete"),
        scope: optional('Scope to delete: "project" (default), "session", or "global" (user-wide). Use "global" only when explicitly asked.'),
      }, []),
      async execute(args) {
        captureEvent("tool_use", {tool: "delete_all_memories"}, apiKey, appId);
        const sp = args.scope ? scopeWriteParams(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, sessionId) : null;
        const res = await mem0.deleteAll({
          user_id: sp ? sp.user_id : (args.agent_id ? args.user_id : (args.user_id ?? userId)),
          app_id: sp ? sp.app_id : (args.app_id ?? appId),
          run_id: sp?.run_id,
          agent_id: args.agent_id,
        } as any);
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "delete_entities",
      description: "Delete entire user/agent/app/run entities and every memory attached to them. Destructive and irreversible -- only on explicit user request to remove a whole user, agent, or project.",
      input: objectSchema({
        user_id: optional("User ID of the entity to delete"),
        agent_id: optional("Agent ID of the entity to delete"),
        app_id: optional("App/Project ID of the entity to delete"),
        run_id: optional("Run ID of the entity to delete"),
      }, []),
      async execute(args) {
        captureEvent("tool_use", {tool: "delete_entities"}, apiKey, appId);
        const res = await mem0.deleteUsers({
          userId: args.user_id,
          agentId: args.agent_id,
          appId: args.app_id,
          runId: args.run_id,
        });
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "list_entities",
      description: "List the user/agent/app/run entities that have memories. Use to discover which scopes exist before searching, listing, or deleting within a specific one.",
      input: objectSchema({
        page: {type: "number", description: "Page number"},
        page_size: {type: "number", description: "Page size"},
      }, []),
      async execute(args) {
        captureEvent("tool_use", {tool: "list_entities"}, apiKey, appId);
        const res = await mem0.users({page: args.page, pageSize: args.page_size});
        return {content: JSON.stringify(res)};
      },
    },
    {
      name: "get_event_status",
      description: "Check whether an asynchronous memory write (add/update/delete) finished, using the event_id that call returned. Poll this when you need to confirm a write was persisted before relying on it.",
      input: objectSchema({
        event_id: {...stringSchema, description: "The ID of the event/async operation to check"},
      }, ["event_id"]),
      async execute(args) {
        captureEvent("tool_use", {tool: "get_event_status"}, apiKey, appId);
        const response = await mem0.client.get(`/v1/event/${args.event_id}/`);
        return {content: JSON.stringify(response.data)};
      },
    },
  ];
}

/**
 * V2 setup: registers the migrated hooks, the memory tools, and the bundled
 * skills/slash commands via the V2 context. Mirrors the V1 factory hook logic
 * (kept intact above for V1 hosts) against the V2 payload shapes.
 */
const Mem0PluginV2 = {
  id: "mem0",
  setup: async (ctx: V2Context): Promise<void> => {
    const apiKey = resolveApiKey(process.env, process.env.HOME || process.env.USERPROFILE || homedir());

    if (!apiKey) {
      v2Log(
        "error",
        "MEM0_API_KEY environment variable not set. Get one at https://app.mem0.ai/dashboard/api-keys",
      );
      return;
    }

    const mem0 = new MemoryClient({apiKey});
    const userId = await getUserId();
    const appId = await getProjectIdV2();
    const branch = await getBranchV2();
    const stats = {adds: 0, searches: 0, messages: 0};
    const sessionId = generateSessionId();
    const globalSearch = loadGlobalSearch();
    const lifecycle = createMemoryLifecycle();
    lifecycle.beginSession();

    let initialized = false;
    let memoryCount = 0;
    let msgCount = 0;

    const systemContext: string[] = [];

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
    try {
      process.on("beforeExit", emitSessionStop);
    } catch {
    }

    Promise.resolve().then(() => autoSetupCategories(mem0, apiKey)).catch(() => {
    });

    function readScopeFilters(args: any): any {
      if (args.scope) return scopeSearchFilters(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, sessionId);
      if (args.filters || args.agent_id) return resolveFilters(args, globalSearch, userId, appId);
      const ds = loadDefaultScope();
      return ds === "project"
        ? resolveFilters(args, globalSearch, userId, appId)
        : scopeSearchFilters(ds, userId, appId, sessionId);
    }

    const memoryFilters = () => (globalSearch ? {OR: [{user_id: "*"}]} : {AND: [{user_id: userId}, {app_id: appId}]});

    // Skills + /mem0-* slash commands (V1 registered these via the `config` hook;
    // V2 exposes dedicated transform editors).
    const skillsDir = discoverSkillsDir();
    if (skillsDir) {
      const skillEntries: Array<{name: string; description: string; path: string; content: string}> = [];
      for (const entry of readdirSync(skillsDir, {withFileTypes: true})) {
        if (!entry.isDirectory()) continue;
        const skillMd = resolve(skillsDir, entry.name, "SKILL.md");
        if (!existsSync(skillMd)) continue;
        let desc = `Mem0 ${entry.name} skill`;
        let content = "";
        try {
          content = readFileSync(skillMd, "utf8");
          const m = content.match(/^description:\s*(.+)$/m);
          if (m) desc = m[1].trim();
        } catch {
        }
        skillEntries.push({name: entry.name, description: desc, path: skillMd, content});
      }

      if (skillEntries.length > 0) {
        await ctx.skill.transform((editor) => {
          for (const skill of skillEntries) {
            editor.add({
              id: skill.name,
              name: skill.name,
              description: skill.description,
              path: skill.path,
              content: skill.content,
            });
          }
        });

        await ctx.command.transform((editor) => {
          for (const skill of skillEntries) {
            editor.add({
              name: skill.name,
              description: skill.description,
              execute: async (input: {sessionID: string; prompt: Record<string, any>; delivery: unknown}) => {
                await ctx.session.prompt({
                  ...input.prompt,
                  sessionID: input.sessionID,
                  text: `Load and execute the \`${skill.name}\` skill.

Use the mem0 memory tools (add_memory, search_memories, get_memories, get_memory, update_memory, delete_memory, delete_all_memories, delete_entities, list_entities, get_event_status) as instructed by the skill.

Identity context (resolved at plugin startup):
- user_id: ${userId}
- app_id: ${appId}
- session_id: ${sessionId}
- branch: ${branch}`,
                  delivery: input.delivery,
                });
              },
            });
          }
        });
      }
    }

    // Memory tools under the V2 tool registry.
    const v2Tools = buildV2Tools({mem0, userId, appId, branch, sessionId, globalSearch, lifecycle, readScopeFilters, apiKey, stats});
    await ctx.tool.transform((editor) => {
      for (const t of v2Tools) editor.add(t);
    });

    // V1 chat.message -> V2 session "prompt"
    await ctx.session.hook("prompt", async (evt) => {
      try {
        const userText = evt?.prompt?.text ?? "";
        if (!userText || userText.length < 10) return;

        const safeText = lifecycle.prepareUserText(userText);
        msgCount++;
        stats.messages++;

        if (!initialized) {
          initialized = true;
          try {
            const all = await mem0.getAll({filters: memoryFilters(), page: 1, pageSize: 1});
            const a: any = all;
            memoryCount =
              typeof a?.count === "number"
                ? a.count
                : Array.isArray(a)
                  ? a.length
                  : Array.isArray(a?.results)
                    ? a.results.length
                    : 0;

            if (globalSearch) {
              systemContext.push(
                `Global search is ON — searches return all memories across all users and projects. Writes still use user_id="${userId}", app_id="${appId}".`,
              );
            } else {
              systemContext.push(
                `Always include user_id="${userId}" and app_id="${appId}" in every search_memories filter and add_memory call.`,
              );
            }

            if (memoryCount === 0) {
              systemContext.push(
                "New project with 0 memories. Capture decisions, conventions, and learnings as you work via the add_memory tool or the remember skill.",
              );
            }

            if (memoryCount > 0) {
              try {
                const res = await mem0.search("recent session state decisions and learnings", {filters: memoryFilters(), topK: 5});
                stats.searches++;
                const memories = extractMemories(res);
                if (memories.length > 0) {
                  const memLines = memories.map((m) => `- ${m.memory}`).join("\n");
                  systemContext.push(`Prior context from mem0:\n${memLines}`);
                }
              } catch {
              }
            }

            systemContext.push(SCOPE_GUIDANCE);
            const activeScope = loadDefaultScope();
            if (activeScope !== "project") {
              systemContext.push(
                `Active default memory scope is "${activeScope}" (set via /mem0-scope). Memory tools use this when no explicit scope is given: "session" limits to this run (run_id="${sessionId}"); "global" spans all your projects (app_id="*"). Pass an explicit scope to override per call. delete_all_memories still requires an explicit scope="global" to delete user-wide.`,
              );
            }
          } catch (err: any) {
            v2Log("error", `Session init error: ${err?.message}`);
          }

          captureEvent("session_start", {memory_count: memoryCount}, apiKey, appId);
        }

        const hasRemember = NUDGE_RE.test(safeText);
        if (hasRemember) {
          systemContext.push(
            "[MEMORY TRIGGER] User asked to remember something. Call add_memory with the user's statement, confidence=1.0, infer=false.",
          );
        }

        const hasResume = RESUME_RE.test(safeText);
        if (hasResume) {
          try {
            const resumeFilters = memoryFilters();
            const [stateRes, decisionsRes] = await Promise.all([
              mem0.search("session state current task", {filters: resumeFilters, topK: 3}),
              mem0.search("recent decisions and learnings", {filters: resumeFilters, topK: 3}),
            ]);
            stats.searches += 2;
            const all = [...extractMemories(stateRes), ...extractMemories(decisionsRes)];
            const seen = new Set<string>();
            const unique = all.filter((m) => {
              if (seen.has(m.id)) return false;
              seen.add(m.id);
              return true;
            });
            if (unique.length > 0) {
              const memLines = unique.map((m) => `- ${m.memory}`).join("\n");
              systemContext.push(`Session resume context:\n${memLines}\n\nThese memories provide context for resuming work.`);
            }
          } catch {
          }
        }

        if (!hasResume && memoryCount > 0) {
          try {
            const res = await mem0.search(safeText, {filters: memoryFilters(), topK: 5});
            stats.searches++;
            const memories = extractMemories(res);
            if (memories.length > 0) {
              const memLines = memories.map((m) => `- ${m.memory}`).join("\n");
              systemContext.push(`Relevant memories:\n${memLines}`);
            }
          } catch {
          }
        }

        if (msgCount % 3 === 0) {
          Promise.resolve().then(async () => {
            try {
              await mem0.add([{role: "user", content: safeText}], {
                user_id: userId,
                app_id: appId,
                metadata: {
                  type: "auto_capture",
                  source: "opencode",
                  confidence: 0.7,
                  session_id: sessionId,
                  branch,
                },
                infer: true,
              } as any);
              stats.adds++;
            } catch {
            }
          });
        }

        if (msgCount % 5 === 0 && stats.adds < Math.floor(msgCount / 3)) {
          systemContext.push(
            "After responding, store any new decisions, learnings, or preferences from this exchange via add_memory. Keep it to 1 sentence per memory.",
          );
        }

        captureEvent("user_prompt", {remember_detected: hasRemember, resume_detected: hasResume}, apiKey, appId);
      } catch (err: any) {
        v2Log("error", `prompt hook failed: ${err?.message}`);
      }
    });

    // V1 experimental.chat.messages.transform -> V2 session "context":
    // the memory block rides in `system` right before the model request.
    const MEMORY_MARKER = "## Mem0 Memory Context";
    await ctx.session.hook("context", async (evt) => {
      try {
        if (systemContext.length === 0 || !Array.isArray(evt?.system)) return;
        if (evt.system.some((p: any) => typeof p?.text === "string" && p.text.includes(MEMORY_MARKER))) return;
        evt.system.push({type: "text", text: `${MEMORY_MARKER}\n\n${systemContext.join("\n\n")}`});
      } catch (err: any) {
        v2Log("error", `context hook failed: ${err?.message}`);
      }
    });

    // V1 tool.execute.before -> V2 tool "execute.before"
    await ctx.tool.hook("execute.before", async (evt) => {
      try {
        const toolName: string = evt?.tool ?? "";
        if (WRITE_TOOLS.has(toolName)) {
          const args: any = evt?.input ?? {};
          const fp = String(args?.file_path ?? args?.filePath ?? "");
          if (/MEMORY\.md|\.claude\/memory/i.test(fp)) {
            throw new Error("Use the add_memory tool instead of writing to MEMORY.md");
          }
        }
      } catch (err: any) {
        if (/add_memory/.test(String(err?.message))) throw err;
        v2Log("error", `execute.before hook failed: ${err?.message}`);
      }
    });

    // V1 tool.execute.after -> V2 tool "execute.after"
    await ctx.tool.hook("execute.after", async (evt) => {
      try {
        const toolName: string = evt?.tool ?? "";
        if (evt?.status !== "completed") return;
        const rawOutput = evt?.result?.content ?? evt?.result?.output;
        const toolOutput = typeof rawOutput === "string" ? rawOutput : Array.isArray(rawOutput)
          ? rawOutput.map((c: any) => (typeof c?.text === "string" ? c.text : "")).join("\n")
          : "";

        if (toolName === "bash" && toolOutput.length >= 50) {
          const command: string = (evt?.input as any)?.command ?? "";
          if (/git\s+(commit|merge|rebase)/.test(command)) return;

          const hasStrongError = ERROR_STRONG_RE.test(toolOutput);
          const multiErrors = (toolOutput.match(ERROR_MULTI_RE) ?? []).length;
          if (!hasStrongError && multiErrors < 2) return;

          const errorLine =
            toolOutput
              .split("\n")
              .find((l: string) => /Error:|Exception:|panic:|FAIL:|fatal:/i.test(l))
              ?.replace(/^\s+/, "")
              .slice(0, 120) ?? "";

          const traceFiles = [
            ...new Set(
              toolOutput.match(
                /[a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh)(:\d+)?/g,
              ) ?? [],
            ),
          ].slice(0, 5);

          const errorQuery = errorLine.slice(0, 80);
          if (errorQuery.length < 10) return;

          captureEvent("bash_error", {error_detected: true}, apiKey, appId);

          const res = await mem0.search(`error: ${errorQuery}`, {filters: memoryFilters(), topK: 6});
          stats.searches++;
          const unique = extractMemories(res);

          let errCtx = `Error detected: \`${command.slice(0, 100)}\` produced:\n> ${errorLine}`;
          if (traceFiles.length > 0) {
            errCtx += `\nFiles in stack trace: ${traceFiles.join(", ")}`;
          }
          if (unique.length > 0) {
            const lines = unique.map((m) => `- ${m.memory}`).join("\n");
            errCtx += `\nPrior error memories:\n${lines}`;
          }
          errCtx += "\nStore resolved errors as anti_pattern or bug_fix memories for future reference.";
          systemContext.push(errCtx);
        }
      } catch {
      }
    });

    // V1 experimental.session.compacting -> V2 session "compaction"
    await ctx.session.hook("compaction", async (evt) => {
      try {
        const compactSessionId = evt?.sessionID ?? sessionId;
        captureEvent(
          "pre_compact",
          {adds: stats.adds, searches: stats.searches, messages: stats.messages},
          apiKey,
          appId,
        );
        const summaryContent = `Session compacting. Project: ${appId}. Branch: ${branch}. Session: ${compactSessionId}. Stats: ${stats.adds} memories stored, ${stats.searches} searches, ${stats.messages} messages.`;
        Promise.resolve().then(async () => {
          try {
            await mem0.add([{role: "user", content: summaryContent}], {
              user_id: userId,
              app_id: appId,
              metadata: {
                type: "session_state",
                source: "pre-compaction",
                session_id: compactSessionId,
                branch,
              },
              infer: true,
            } as any);
          } catch {
          }
        });

        const res = await mem0.search("session state decisions learnings", {filters: memoryFilters(), topK: 10});
        const memories = extractMemories(res);
        if (memories.length > 0 && Array.isArray(evt?.system)) {
          const lines = memories.map((m) => `- ${m.memory}`).join("\n");
          evt.system.push({
            type: "text",
            text: `## Mem0 Memories (preserve across compaction)\n\n${lines}\n\nIMPORTANT: After compaction, store any key decisions or learnings using the add_memory tool.`,
          });
        }
      } catch {
      }
    });

    // V1 shell.env -> V2 shell "create.before"
    await ctx.shell.hook("create.before", async (evt) => {
      if (evt?.env) {
        evt.env.MEM0_USER_ID = userId;
        evt.env.MEM0_APP_ID = appId;
        evt.env.MEM0_SESSION_ID = sessionId;
        evt.env.MEM0_BRANCH = branch;
        evt.env.MEM0_GLOBAL_SEARCH = globalSearch ? "true" : "false";
      }
    });
  },
};

/**
 * Dual-shape default export (OpenCode V1->V2 migration guide):
 * - V2 hosts decode `{ id, setup }` and run `setup(ctx)`.
 * - V1 hosts (>= 1.18.29) decode the `server` key and call `Mem0Plugin(ctx)`.
 */
const Mem0PluginModule: Mem0PluginModule = {
  ...Mem0PluginV2,
  server: Mem0Plugin,
};

export default Mem0PluginModule;
