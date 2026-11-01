import { resolveToolScope } from "../agent-plugin-core/typescript/src/scoping.ts";
// Mem0 memory plugin for OpenCode V2: captures and recalls memories across sessions
// (add / search / manage) via the Mem0 platform, wired through OpenCode plugin hooks.
// Memory operations are exposed as native OpenCode tools backed by the mem0ai SDK
// (no MCP server required).
//
// OpenCode V2 loads a plugin's default export only when it is an object of the form
// `{ id, effect(host) }` or `{ id, setup(ctx) }`. The previous V1 function-style
// plugin (`(ctx) => ({ tool: ... })`) was rejected by the V2 loader with
// "Plugin must export a default definition with an id and an effect or setup
// function." (mem0ai/mem0#7602). This file is the `setup`-style migration.
import type { Context as PluginContext, Plugin } from "@opencode/plugin/promise/plugin";
import { MemoryClient } from "mem0ai";
import { userInfo } from "os";
import { basename, resolve, dirname } from "path";
import { randomBytes } from "crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync } from "fs";
import { homedir } from "os";
import { join } from "path";
import { createHash } from "crypto";
import { execFileSync } from "child_process";
import { captureEvent } from "./telemetry";
import { asScope, scopeSearchFilters, scopeWriteParams, resolveDefaultScope, SCOPE_GUIDANCE, type Scope } from "./scope";
import { parseProjectFromRemote } from "./project";
import { resolveApiKey } from "./api-key";
import { createMemoryLifecycle } from "../agent-plugin-core/typescript/src/lifecycle.ts";
import { SEARCH_QUERY_DESCRIPTION, SEARCH_TOOL_DESCRIPTION } from "../agent-plugin-core/typescript/src/prompts.ts";

async function getUserId(): Promise<string> {
  if (process.env.MEM0_USER_ID) return process.env.MEM0_USER_ID;
  try {
    return userInfo().username;
  } catch {
  }
  return process.env.USER || process.env.USERNAME || "unknown";
}

/** Run git and return trimmed stdout, or undefined when it fails. */
function git(args: string[]): string | undefined {
  try {
    return execFileSync("git", args, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return undefined;
  }
}

async function getProjectId(): Promise<string> {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
  // Prefer the git remote's owner/repo — stable across clones, worktrees, and
  // sub-directories (handles https + ssh, incl. custom host aliases).
  const remote = git(["remote", "get-url", "origin"]);
  if (remote) {
    const project = parseProjectFromRemote(remote);
    if (project) return project;
  }
  // No usable remote: use the git repo ROOT dir name, not cwd (which may be a
  // sub-directory, or your home dir if OpenCode was launched outside a repo).
  const top = git(["rev-parse", "--show-toplevel"]);
  if (top) return basename(top);
  return basename(process.cwd());
}

async function getBranch(): Promise<string> {
  // NOTE: the V1 plugin executed git through the `$` the OpenCode runtime
  // injected into plugin context; the V2 promise API has no `$`, so run git
  // directly. Behavior is unchanged.
  return git(["branch", "--show-current"]) || "main";
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

/** Tool argument shapes (decoded by OpenCode from the JSON Schemas below). */
interface AddMemoryArgs {
  text: string;
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  metadata?: Record<string, any>;
  infer?: boolean;
  scope?: string;
}
interface SearchMemoriesArgs {
  query: string;
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  filters?: Record<string, any>;
  limit?: number;
  top_k?: number;
  scope?: string;
}
interface GetMemoriesArgs {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  filters?: Record<string, any>;
  page?: number;
  page_size?: number;
  scope?: string;
}
interface GetMemoryArgs {
  id: string;
}
interface UpdateMemoryArgs {
  id: string;
  text?: string;
  metadata?: Record<string, any>;
}
interface DeleteMemoryArgs {
  id: string;
}
interface DeleteAllMemoriesArgs {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  scope?: string;
}
interface DeleteEntitiesArgs {
  user_id?: string;
  agent_id?: string;
  app_id?: string;
  run_id?: string;
}
interface ListEntitiesArgs {
  page?: number;
  page_size?: number;
}
interface GetEventStatusArgs {
  event_id: string;
}

/**
 * A tool contributed through `ctx.tool.transform`.
 *
 * `input` is a plain JSON Schema (draft 2020-12) document, not an Effect Schema:
 * OpenCode accepts raw JSON Schemas in `Tool.ValueSchema` and decodes them
 * host-side, so the bundle carries no `effect` copy and cannot drift against the
 * host's schema runtime. `execute` returns `content`, which OpenCode renders as
 * the tool's visible output (the V1 plugin returned a plain string).
 */
interface ToolDef<A> {
  name: string;
  description: string;
  input: object;
  execute: (args: A, _context: unknown) => Promise<{ content: string }>;
}

/** Strip a `---`-fenced YAML frontmatter the same way OpenCode's skill loader does. */
function parseSkillMarkdown(raw: string): { name?: string; description?: string; body: string } {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return { body: raw };
  let name: string | undefined;
  let description: string | undefined;
  for (const line of m[1].split(/\r?\n/)) {
    const fm = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!fm) continue;
    if (fm[1] === "name") name = fm[2].trim();
    else if (fm[1] === "description") description = fm[2].trim();
  }
  return { name, description, body: raw.slice(m[0].length) };
}

/**
 * Register the bundled `opencode-skills` with OpenCode.
 *
 * The V1 plugin did this through the `config` hook (`skills.paths`), which has no
 * V2 promise equivalent — the V2 Context exposes no config surface. Registering
 * each skill through `ctx.skill.transform` puts the same skills in front of the
 * agent's skill tool, which preserves the essential behavior.
 *
 * Intentionally dropped: the V1 `config.command` slash-command templates. V2
 * commands are executables (`ctx.command.transform`), not prompt templates, so
 * mapping them would have changed behavior rather than preserved it; see the
 * commit/report notes.
 */
function registerSkills(ctx: PluginContext) {
  const here = import.meta.filename;
  const skillsDir = [
    resolve(dirname(dirname(here)), "opencode-skills"),
    resolve(dirname(here), "opencode-skills"),
  ].find(existsSync);
  if (!skillsDir) return;

  ctx.skill.transform((editor) => {
    for (const entry of readdirSync(skillsDir, {withFileTypes: true})) {
      if (!entry.isDirectory()) continue;
      const skillMd = resolve(skillsDir, entry.name, "SKILL.md");
      if (!existsSync(skillMd)) continue;

      let parsed: {name?: string; description?: string; body: string} | undefined;
      try {
        parsed = parseSkillMarkdown(readFileSync(skillMd, "utf8"));
      } catch {
      }
      if (!parsed) continue;
      // Skill.Info carries branded id/name/path types; cast at this boundary so
      // the bundle needs no runtime import from the OpenCode SDK (types only).
      editor.add({
        id: entry.name,
        name: parsed.name ?? entry.name,
        description: parsed.description ?? `Mem0 ${entry.name} skill`,
        path: skillMd,
        content: parsed.body,
      } as any);
    }
  });
}

const Mem0Plugin: Plugin = {
  id: "mem0",
  setup: async (ctx) => {
    const apiKey = resolveApiKey(process.env, process.env.HOME || process.env.USERPROFILE || homedir());

    if (!apiKey) {
      // The V1 plugin logged through `client.app.log`; the V2 promise Context has
      // no client/app-log surface, so fall back to the server console.
      console.error(
        "mem0 plugin: MEM0_API_KEY environment variable not set. Get one at https://app.mem0.ai/dashboard/api-keys",
      );
      // Match the V1 behavior: no key, no tools.
      return;
    }

    const mem0 = new MemoryClient({apiKey});
    const userId = await getUserId();
    const appId = await getProjectId();
    const branch = await getBranch();
    const stats = {adds: 0, searches: 0, messages: 0};
    const sessionId = generateSessionId();
    const globalSearch = loadGlobalSearch();
    const lifecycle = createMemoryLifecycle();
    lifecycle.beginSession();

    let initialized = false;
    let memoryCount = 0;
    let msgCount = 0;

    const systemContext: string[] = [];

    // Emit a session_stop telemetry event once when the process winds down (or
    // when OpenCode disposes the plugin).
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

    registerSkills(ctx);

    // Resolve read filters for the memory tools. Precedence: an explicit `scope`
    // arg wins; then explicit `filters`/`agent_id`; otherwise fall back to the
    // user's persisted default scope (read fresh so the scope skill applies at once).
    // A "project" default preserves the existing behavior, including global_search.
    function readScopeFilters(args: any): any {
      if (args.scope) return scopeSearchFilters(resolveToolScope(asScope(args.scope), loadDefaultScope()), userId, appId, sessionId);
      if (args.filters || args.agent_id) return resolveFilters(args, globalSearch, userId, appId);
      const ds = loadDefaultScope();
      return ds === "project"
        ? resolveFilters(args, globalSearch, userId, appId)
        : scopeSearchFilters(ds, userId, appId, sessionId);
    }

    // ---- Tools -----------------------------------------------------------
    // V2 tools are registered through `ctx.tool.transform` with `{ name,
    // description, input, execute }`; the V1 `tool: { add_memory: tool(...) }`
    // map has no V2 equivalent. The single `as any` below erases the generic
    // schema types at the registration boundary, mirroring how the OpenCode
    // registry itself erases tool definitions after `add`.
    const tools: ToolDef<any>[] = [
      {
        name: "add_memory",
        description: "Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something. Set infer to false to store the memory verbatim without LLM fact extraction.",
        input: {
          type: "object",
          properties: {
            text: {type: "string", description: "Memory text content"},
            user_id: {type: "string", description: "User ID"},
            app_id: {type: "string", description: "App/Project ID"},
            agent_id: {type: "string", description: "Agent ID"},
            metadata: {type: "object", description: "Metadata key-value pairs"},
            infer: {type: "boolean", description: "Set to false to store memory verbatim without LLM fact extraction"},
            scope: {type: "string", description: 'Write scope: "project" (this repo, default), "session" (this run), or "global" (user-wide, all projects). Use "global" only when explicitly asked.'},
          },
          required: ["text"],
        },
        async execute(args: AddMemoryArgs) {
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
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "search_memories",
        description: SEARCH_TOOL_DESCRIPTION,
        input: {
          type: "object",
          properties: {
            query: {type: "string", description: SEARCH_QUERY_DESCRIPTION},
            user_id: {type: "string", description: "User ID"},
            app_id: {type: "string", description: "App/Project ID"},
            agent_id: {type: "string", description: "Agent ID"},
            filters: {type: "object", description: "Key-value filters (e.g. metadata or user/app filters)"},
            limit: {type: "number", description: "Maximum number of results to return (top_k)"},
            top_k: {type: "number", description: "Maximum number of results to return (alternative parameter)"},
            scope: {type: "string", description: 'Search scope: "project" (this repo, default), "session" (this run only), or "global" (across ALL your projects). Only use "global" when the user explicitly asks to search across projects.'},
          },
          required: ["query"],
        },
        async execute(args: SearchMemoriesArgs) {
          stats.searches++;
          captureEvent("tool_use", {tool: "search_memories"}, apiKey, appId);
          const topK = args.limit ?? args.top_k ?? 10;
          const filters = readScopeFilters(args);

          const res = await mem0.search(lifecycle.prepareUserText(args.query), {
            filters,
            topK,
          });
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "get_memories",
        description: "List or browse stored memories without a search query -- useful for auditing what is remembered or paging through everything in a scope. To find memories relevant to a question, use search_memories instead (it ranks by semantic relevance).",
        input: {
          type: "object",
          properties: {
            user_id: {type: "string", description: "User ID"},
            app_id: {type: "string", description: "App/Project ID"},
            agent_id: {type: "string", description: "Agent ID"},
            filters: {type: "object", description: "Metadata/identity filters"},
            page: {type: "number", description: "Page number"},
            page_size: {type: "number", description: "Page size"},
            scope: {type: "string", description: 'Scope: "project" (default), "session", or "global" (across ALL your projects). Use "global" only when explicitly asked.'},
          },
        },
        async execute(args: GetMemoriesArgs) {
          captureEvent("tool_use", {tool: "get_memories"}, apiKey, appId);
          const filters = readScopeFilters(args);

          const res = await mem0.getAll({
            page: args.page,
            pageSize: args.page_size,
            filters,
          });
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "get_memory",
        description: "Fetch one memory by its exact ID (e.g. an ID returned by search_memories or get_memories) to read its full content and metadata.",
        input: {
          type: "object",
          properties: {
            id: {type: "string", description: "The ID of the memory to retrieve"},
          },
          required: ["id"],
        },
        async execute(args: GetMemoryArgs) {
          captureEvent("tool_use", {tool: "get_memory"}, apiKey, appId);
          const res = await mem0.get(args.id);
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "update_memory",
        description: "Update an existing memory in place when a stored fact has changed -- requires the memory ID. Preserves the ID and history, so prefer this over deleting and re-adding.",
        input: {
          type: "object",
          properties: {
            id: {type: "string", description: "The ID of the memory to update"},
            text: {type: "string", description: "New text content for the memory"},
            metadata: {type: "object", description: "New metadata key-value pairs"},
          },
          required: ["id"],
        },
        async execute(args: UpdateMemoryArgs) {
          captureEvent("tool_use", {tool: "update_memory"}, apiKey, appId);
          const res = await mem0.update(args.id, {
            text:
              args.text === undefined
                ? undefined
                : lifecycle.prepareUserText(args.text),
            metadata: args.metadata,
          });
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "delete_memory",
        description: "Delete one or more memories by ID when they are wrong, obsolete, or the user asks to forget them. Irreversible -- only delete what is clearly no longer wanted.",
        input: {
          type: "object",
          properties: {
            id: {type: "string", description: "The ID of the memory to delete"},
          },
          required: ["id"],
        },
        async execute(args: DeleteMemoryArgs) {
          captureEvent("tool_use", {tool: "delete_memory"}, apiKey, appId);
          const res = await mem0.delete(args.id);
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "delete_all_memories",
        description: "Delete ALL memories in the given scope. Destructive and irreversible -- only use when the user explicitly asks to wipe their memory. Never call speculatively.",
        input: {
          type: "object",
          properties: {
            user_id: {type: "string", description: "User ID whose memories to delete"},
            app_id: {type: "string", description: "App ID whose memories to delete"},
            agent_id: {type: "string", description: "Agent ID whose memories to delete"},
            scope: {type: "string", description: 'Scope to delete: "project" (default), "session", or "global" (user-wide). Use "global" only when explicitly asked.'},
          },
        },
        async execute(args: DeleteAllMemoriesArgs) {
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
        input: {
          type: "object",
          properties: {
            user_id: {type: "string", description: "User ID of the entity to delete"},
            agent_id: {type: "string", description: "Agent ID of the entity to delete"},
            app_id: {type: "string", description: "App/Project ID of the entity to delete"},
            run_id: {type: "string", description: "Run ID of the entity to delete"},
          },
        },
        async execute(args: DeleteEntitiesArgs) {
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
        input: {
          type: "object",
          properties: {
            page: {type: "number", description: "Page number"},
            page_size: {type: "number", description: "Page size"},
          },
        },
        async execute(args: ListEntitiesArgs) {
          captureEvent("tool_use", {tool: "list_entities"}, apiKey, appId);
          const res = await mem0.users({
            page: args.page,
            pageSize: args.page_size,
          });
          return {content: JSON.stringify(res)};
        },
      },

      {
        name: "get_event_status",
        description: "Check whether an asynchronous memory write (add/update/delete) finished, using the event_id that call returned. Poll this when you need to confirm a write was persisted before relying on it.",
        input: {
          type: "object",
          properties: {
            event_id: {type: "string", description: "The ID of the event/async operation to check"},
          },
          required: ["event_id"],
        },
        async execute(args: GetEventStatusArgs) {
          captureEvent("tool_use", {tool: "get_event_status"}, apiKey, appId);
          const response = await mem0.client.get(`/v1/event/${args.event_id}/`);
          return {content: JSON.stringify(response.data)};
        },
      },
    ];
    ctx.tool.transform((editor) => {
      for (const tool of tools) editor.add(tool as any);
      // Visible in the OpenCode server log; keeps install troubleshooting easy.
      console.info(`mem0 plugin: registered ${tools.length} memory tools`);
    });

    // ---- User-prompt hook (V1 "chat.message") -----------------------------
    // V2 has no per-part chat message hook; `session.hook("prompt")` fires once
    // per admitted user prompt with the prompt text, which is exactly the text
    // the V1 hook used to extract from the message parts.
    ctx.session.hook("prompt", async (event) => {
      const userText: string = event.prompt.text;
      const safeText = lifecycle.prepareUserText(userText);
      if (safeText.length < 10) return;

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
              `Active default memory scope is "${activeScope}" (set via the mem0-scope skill). Memory tools use this when no explicit scope is given: "session" limits to this run (run_id="${sessionId}"); "global" spans all your projects (app_id="*"). Pass an explicit scope to override per call. delete_all_memories still requires an explicit scope="global" to delete user-wide.`,
            );
          }
        } catch (err: any) {
          // V1 logged via client.app.log; the V2 promise Context has no app-log
          // surface, so fall back to the server console.
          console.error(`mem0 plugin: session init error: ${err?.message}`);
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
    });

    // ---- Context hook (V1 "experimental.chat.messages.transform") ---------
    // V2 plugins mutate the outgoing request through `session.hook("context")`.
    // The accumulated memory context goes into the request's system parts
    // instead of being spliced into the first user message; same visibility,
    // simpler and more robust.
    ctx.session.hook("context", (event) => {
      if (systemContext.length === 0) return;
      const block = `## Mem0 Memory Context\n\n${systemContext.join("\n\n")}`;
      if (event.system.some((part) => part.type === "text" && part.text.includes("## Mem0 Memory Context"))) return;
      event.system.push({type: "text", text: block});
    });

    // ---- Tool execution hooks (V1 "tool.execute.before"/".after") ---------
    ctx.tool.hook("execute.before", async (event) => {
      const toolName: string = event.tool ?? "";

      if (WRITE_TOOLS.has(toolName)) {
        const input = event.input as Record<string, any> | undefined;
        const fp = String(input?.file_path ?? input?.filePath ?? "");
        if (/MEMORY\.md|\.claude\/memory/i.test(fp)) {
          throw new Error(
            "Use the add_memory tool instead of writing to MEMORY.md",
          );
        }
      }
    });

    ctx.tool.hook("execute.after", async (event) => {
      try {
        const toolName: string = event.tool ?? "";
        const input = event.input as Record<string, any> | undefined;
        // V1 received the tool's returned text as `output.output`; V2 exposes a
        // discriminated result (status "completed" | "error").
        if (event.status !== "completed") return;
        const result: Record<string, any> = event.result as Record<string, any>;
        const content = result?.content ?? result?.output;
        const toolOutput = typeof content === "string" ? content : (content ? JSON.stringify(content) : "");

        if (toolName === "bash" && toolOutput.length >= 50) {
          const command: string = input?.command ?? "";
          if (/git\s+(commit|merge|rebase)/.test(command)) return;

          const hasStrongError = ERROR_STRONG_RE.test(toolOutput);
          const multiErrors = (toolOutput.match(ERROR_MULTI_RE) ?? []).length;
          if (!hasStrongError && multiErrors < 2) return;

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
        }
      } catch {
      }
    });

    // ---- Compaction hook (V1 "experimental.session.compacting") -----------
    // V2 exposes the same "runs before the LLM writes the continuation
    // summary" moment as `session.hook("compaction")`. It has no dedicated
    // context-string-array output; system parts are part of the compaction
    // model request, so the preserve-across-compaction block is appended there.
    ctx.session.hook("compaction", async (event) => {
      try {
        const compactSessionId = event.sessionID;
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
        if (memories.length > 0) {
          const lines = memories.map((m) => `- ${m.memory}`).join("\n");
          event.system.push({
            type: "text",
            text: `## Mem0 Memories (preserve across compaction)\n\n${lines}\n\nIMPORTANT: After compaction, store any key decisions or learnings using the add_memory tool.`,
          });
        }
      } catch {
      }
    });

    // ---- Shell env hook (V1 "shell.env") ---------------------------------
    ctx.shell.hook("create.before", (event) => {
      event.env.MEM0_USER_ID = userId;
      event.env.MEM0_APP_ID = appId;
      event.env.MEM0_SESSION_ID = sessionId;
      event.env.MEM0_BRANCH = branch;
      event.env.MEM0_GLOBAL_SEARCH = globalSearch ? "true" : "false";
    });

    return () => {
      try {
        emitSessionStop();
        process.off("beforeExit", emitSessionStop);
      } catch {
      }
    };
  },
};

export default Mem0Plugin;