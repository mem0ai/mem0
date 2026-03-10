/**
 * OpenClaw Memory (Mem0) Plugin
 *
 * Long-term memory via Mem0 — supports both the Mem0 platform
 * and the open-source self-hosted SDK. Uses the official `mem0ai` package.
 *
 * Features:
 * - 5 tools: memory_search, memory_list, memory_store, memory_get, memory_forget
 *   (with session/long-term scope support via scope and longTerm parameters)
 * - Short-term (session-scoped) and long-term (user-scoped) memory
 * - Auto-recall: injects relevant memories (both scopes) before each agent turn
 * - Auto-capture: stores key facts scoped to the current session after each agent turn
 * - Per-agent isolation: multi-agent setups write/read from separate userId namespaces
 *   automatically via sessionKey routing (zero breaking changes for single-agent setups)
 * - CLI: openclaw mem0 search, openclaw mem0 stats
 * - Dual mode: platform or open-source (self-hosted)
 */

import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

// ============================================================================
// Types
// ============================================================================

type Mem0Mode = "platform" | "open-source";

type Mem0Config = {
  mode: Mem0Mode;
  // Platform-specific
  apiKey?: string;
  orgId?: string;
  projectId?: string;
  customInstructions: string;
  customCategories: Record<string, string>;
  enableGraph: boolean;
  // OSS-specific
  customPrompt?: string;
  oss?: {
    embedder?: { provider: string; config: Record<string, unknown> };
    vectorStore?: { provider: string; config: Record<string, unknown> };
    llm?: { provider: string; config: Record<string, unknown> };
    historyDbPath?: string;
    disableHistory?: boolean;
  };
  // Shared
  userId: string;
  autoCapture: boolean;
  autoRecall: boolean;
  searchThreshold: number;
  topK: number;
};

// Unified types for the provider interface
interface AddOptions {
  user_id: string;
  run_id?: string;
  custom_instructions?: string;
  custom_categories?: Array<Record<string, string>>;
  enable_graph?: boolean;
  output_format?: string;
  source?: string;
}

interface SearchOptions {
  user_id: string;
  run_id?: string;
  top_k?: number;
  threshold?: number;
  limit?: number;
  keyword_search?: boolean;
  reranking?: boolean;
  source?: string;
}

interface ListOptions {
  user_id: string;
  run_id?: string;
  page_size?: number;
  source?: string;
}

interface MemoryItem {
  id: string;
  memory: string;
  user_id?: string;
  score?: number;
  categories?: string[];
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

interface AddResultItem {
  id: string;
  memory: string;
  event: "ADD" | "UPDATE" | "DELETE" | "NOOP";
}

interface AddResult {
  results: AddResultItem[];
}

// ============================================================================
// Unified Provider Interface
// ============================================================================

interface Mem0Provider {
  add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult>;
  search(query: string, options: SearchOptions): Promise<MemoryItem[]>;
  get(memoryId: string): Promise<MemoryItem>;
  getAll(options: ListOptions): Promise<MemoryItem[]>;
  delete(memoryId: string): Promise<void>;
}

// ============================================================================
// Platform Provider (Mem0 Cloud)
// ============================================================================

class PlatformProvider implements Mem0Provider {
  private client: any; // MemoryClient from mem0ai
  private initPromise: Promise<void> | null = null;

  constructor(
    private readonly apiKey: string,
    private readonly orgId?: string,
    private readonly projectId?: string,
  ) { }

  private async ensureClient(): Promise<void> {
    if (this.client) return;
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._init().catch((err) => {
      this.initPromise = null;
      throw err;
    });
    return this.initPromise;
  }

  private async _init(): Promise<void> {
    const { default: MemoryClient } = await import("mem0ai");
    const opts: { apiKey: string; org_id?: string; project_id?: string } = { apiKey: this.apiKey };
    if (this.orgId) opts.org_id = this.orgId;
    if (this.projectId) opts.project_id = this.projectId;
    this.client = new MemoryClient(opts);
  }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    await this.ensureClient();
    const opts: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) opts.run_id = options.run_id;
    if (options.custom_instructions)
      opts.custom_instructions = options.custom_instructions;
    if (options.custom_categories)
      opts.custom_categories = options.custom_categories;
    if (options.enable_graph) opts.enable_graph = options.enable_graph;
    if (options.output_format) opts.output_format = options.output_format;
    if (options.source) opts.source = options.source;

    const result = await this.client.add(messages, opts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    const filters: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) filters.run_id = options.run_id;

    const opts: Record<string, unknown> = {
      api_version: "v2",
      filters,
    };
    if (options.top_k != null) opts.top_k = options.top_k;
    if (options.threshold != null) opts.threshold = options.threshold;
    if (options.keyword_search != null) opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.rerank = options.reranking;

    const results = await this.client.search(query, opts);
    return normalizeSearchResults(results);
  }

  async get(memoryId: string): Promise<MemoryItem> {
    await this.ensureClient();
    const result = await this.client.get(memoryId);
    return normalizeMemoryItem(result);
  }

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    await this.ensureClient();
    const opts: Record<string, unknown> = { user_id: options.user_id };
    if (options.run_id) opts.run_id = options.run_id;
    if (options.page_size != null) opts.page_size = options.page_size;
    if (options.source) opts.source = options.source;

    const results = await this.client.getAll(opts);
    if (Array.isArray(results)) return results.map(normalizeMemoryItem);
    // Some versions return { results: [...] }
    if (results?.results && Array.isArray(results.results))
      return results.results.map(normalizeMemoryItem);
    return [];
  }

  async delete(memoryId: string): Promise<void> {
    await this.ensureClient();
    await this.client.delete(memoryId);
  }
}

// ============================================================================
// Open-Source Provider (Self-hosted)
// ============================================================================

class OSSProvider implements Mem0Provider {
  private memory: any; // Memory from mem0ai/oss
  private initPromise: Promise<void> | null = null;

  constructor(
    private readonly ossConfig?: Mem0Config["oss"],
    private readonly customPrompt?: string,
    private readonly resolvePath?: (p: string) => string,
  ) { }

  private async ensureMemory(): Promise<void> {
    if (this.memory) return;
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._init().catch((err) => {
      this.initPromise = null;
      throw err;
    });
    return this.initPromise;
  }

  private async _init(): Promise<void> {
    const { Memory } = await import("mem0ai/oss");

    const config: Record<string, unknown> = { version: "v1.1" };

    if (this.ossConfig?.embedder) config.embedder = this.ossConfig.embedder;
    if (this.ossConfig?.vectorStore)
      config.vectorStore = this.ossConfig.vectorStore;
    if (this.ossConfig?.llm) config.llm = this.ossConfig.llm;

    if (this.ossConfig?.historyDbPath) {
      const dbPath = this.resolvePath
        ? this.resolvePath(this.ossConfig.historyDbPath)
        : this.ossConfig.historyDbPath;
      config.historyDbPath = dbPath;
    }

    if (this.ossConfig?.disableHistory) {
      config.disableHistory = true;
    }

    if (this.customPrompt) config.customPrompt = this.customPrompt;

    try {
      this.memory = new Memory(config);
    } catch (err) {
      // If initialization fails (e.g. native SQLite binding resolution under
      // jiti), retry with history disabled — the history DB is the most common
      // source of native-binding failures and is not required for core
      // memory operations.
      if (!config.disableHistory) {
        console.warn(
          "[mem0] Memory initialization failed, retrying with history disabled:",
          err instanceof Error ? err.message : err,
        );
        config.disableHistory = true;
        this.memory = new Memory(config);
      } else {
        throw err;
      }
    }
  }

  async add(
    messages: Array<{ role: string; content: string }>,
    options: AddOptions,
  ): Promise<AddResult> {
    await this.ensureMemory();
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const addOpts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) addOpts.runId = options.run_id;
    if (options.source) addOpts.source = options.source;
    const result = await this.memory.add(messages, addOpts);
    return normalizeAddResult(result);
  }

  async search(query: string, options: SearchOptions): Promise<MemoryItem[]> {
    await this.ensureMemory();
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const opts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) opts.runId = options.run_id;
    if (options.limit != null) opts.limit = options.limit;
    else if (options.top_k != null) opts.limit = options.top_k;
    if (options.keyword_search != null) opts.keyword_search = options.keyword_search;
    if (options.reranking != null) opts.reranking = options.reranking;
    if (options.source) opts.source = options.source;
    if (options.threshold != null) opts.threshold = options.threshold;

    const results = await this.memory.search(query, opts);
    const normalized = normalizeSearchResults(results);

    // Filter results by threshold if specified (client-side filtering as fallback)
    if (options.threshold != null) {
      return normalized.filter(item => (item.score ?? 0) >= options.threshold!);
    }

    return normalized;
  }

  async get(memoryId: string): Promise<MemoryItem> {
    await this.ensureMemory();
    const result = await this.memory.get(memoryId);
    return normalizeMemoryItem(result);
  }

  async getAll(options: ListOptions): Promise<MemoryItem[]> {
    await this.ensureMemory();
    // OSS SDK uses camelCase: userId/runId, not user_id/run_id
    const getAllOpts: Record<string, unknown> = { userId: options.user_id };
    if (options.run_id) getAllOpts.runId = options.run_id;
    if (options.source) getAllOpts.source = options.source;
    const results = await this.memory.getAll(getAllOpts);
    if (Array.isArray(results)) return results.map(normalizeMemoryItem);
    if (results?.results && Array.isArray(results.results))
      return results.results.map(normalizeMemoryItem);
    return [];
  }

  async delete(memoryId: string): Promise<void> {
    await this.ensureMemory();
    await this.memory.delete(memoryId);
  }
}

// ============================================================================
// Result Normalizers
// ============================================================================

function normalizeMemoryItem(raw: any): MemoryItem {
  return {
    id: raw.id ?? raw.memory_id ?? "",
    memory: raw.memory ?? raw.text ?? raw.content ?? "",
    // Handle both platform (user_id, created_at) and OSS (userId, createdAt) field names
    user_id: raw.user_id ?? raw.userId,
    score: raw.score,
    categories: raw.categories,
    metadata: raw.metadata,
    created_at: raw.created_at ?? raw.createdAt,
    updated_at: raw.updated_at ?? raw.updatedAt,
  };
}

function normalizeSearchResults(raw: any): MemoryItem[] {
  // Platform API returns flat array, OSS returns { results: [...] }
  if (Array.isArray(raw)) return raw.map(normalizeMemoryItem);
  if (raw?.results && Array.isArray(raw.results))
    return raw.results.map(normalizeMemoryItem);
  return [];
}

function normalizeAddResult(raw: any): AddResult {
  // Handle { results: [...] } shape (both platform and OSS)
  if (raw?.results && Array.isArray(raw.results)) {
    return {
      results: raw.results.map((r: any) => ({
        id: r.id ?? r.memory_id ?? "",
        memory: r.memory ?? r.text ?? "",
        // Platform API may return PENDING status (async processing)
        // OSS stores event in metadata.event
        event: r.event ?? r.metadata?.event ?? (r.status === "PENDING" ? "ADD" : "ADD"),
      })),
    };
  }
  // Platform API without output_format returns flat array
  if (Array.isArray(raw)) {
    return {
      results: raw.map((r: any) => ({
        id: r.id ?? r.memory_id ?? "",
        memory: r.memory ?? r.text ?? "",
        event: r.event ?? r.metadata?.event ?? (r.status === "PENDING" ? "ADD" : "ADD"),
      })),
    };
  }
  return { results: [] };
}

// ============================================================================
// Config Parser
// ============================================================================

function resolveEnvVars(value: string): string {
  return value.replace(/\$\{([^}]+)\}/g, (_, envVar) => {
    const envValue = process.env[envVar];
    if (!envValue) {
      throw new Error(`Environment variable ${envVar} is not set`);
    }
    return envValue;
  });
}

function resolveEnvVarsDeep(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === "string") {
      result[key] = resolveEnvVars(value);
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      result[key] = resolveEnvVarsDeep(value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  }
  return result;
}

// ============================================================================
// Default Custom Instructions & Categories
// ============================================================================

const DEFAULT_CUSTOM_INSTRUCTIONS = `Your Task: Extract durable, actionable facts from conversations between a user and an AI assistant. Only store information that would be useful to an agent in a FUTURE session, days or weeks later.

Before storing any fact, ask: "Would a new agent — with no prior context — benefit from knowing this?" If the answer is no, do not store it.

Information to Extract (in priority order):

1. Configuration & System State Changes:
   - Tools/services configured, installed, or removed (with versions/dates)
   - Model assignments for agents, API keys configured (NEVER the key itself — see Exclude)
   - Cron schedules, automation pipelines, deployment configurations
   - Architecture decisions (agent hierarchy, system design, deployment strategy)
   - Specific identifiers: file paths, sheet IDs, channel IDs, user IDs, folder IDs

2. Standing Rules & Policies:
   - Explicit user directives about behavior ("never create accounts without consent")
   - Workflow policies ("each agent must review model selection before completing a task")
   - Security constraints, permission boundaries, access patterns

3. Identity & Demographics:
   - Name, location, timezone, language preferences
   - Occupation, employer, job role, industry

4. Preferences & Opinions:
   - Communication style preferences
   - Tool and technology preferences (with specifics: versions, configs)
   - Strong opinions or values explicitly stated
   - The WHY behind preferences when stated

5. Goals, Projects & Milestones:
   - Active projects (name, description, current status)
   - Completed setup milestones ("ElevenLabs fully configured as of 2026-02-20")
   - Deadlines, roadmaps, and progress tracking
   - Problems actively being solved

6. Technical Context:
   - Tech stack, tools, development environment
   - Agent ecosystem structure (names, roles, relationships)
   - Skill levels in different areas

7. Relationships & People:
   - Names and roles of people mentioned (colleagues, family, clients)
   - Team structure, key contacts

8. Decisions & Lessons:
   - Important decisions made and their reasoning
   - Lessons learned, strategies that worked or failed

Guidelines:

TEMPORAL ANCHORING (critical):
- ALWAYS include temporal context for time-sensitive facts using "As of YYYY-MM-DD, ..."
- Extract dates from message timestamps, dates mentioned in the text, or the system-provided current date
- If no date is available, note "date unknown" rather than omitting temporal context
- Examples: "As of 2026-02-20, ElevenLabs setup is complete" NOT "ElevenLabs setup is complete"

CONCISENESS:
- Each memory should be 1-2 sentences, self-contained, and in third person
- "User's Tailscale machine 'mac' (IP 100.71.135.41) is configured under beau@rizedigital.io (as of 2026-02-20)"
- NOT a paragraph retelling the whole conversation

OUTCOMES OVER INTENT:
- When an assistant message summarizes completed work, extract the durable OUTCOMES
- "Call scripts sheet (ID: 146Qbb...) was updated with truth-based templates" NOT "User wants to update call scripts"
- Extract what WAS DONE, not what was requested

DEDUPLICATION:
- Before creating a new memory, check if a substantially similar fact already exists
- If so, UPDATE the existing memory with any new details rather than creating a duplicate

LANGUAGE:
- ALWAYS preserve the original language of the conversation
- If the user speaks Spanish, store the memory in Spanish; do not translate

Exclude (NEVER store):
- Passwords, API keys, tokens, secrets, or any credentials — even if shared in conversation. Instead store: "Tavily API key was configured and saved to .env (as of 2026-02-20)"
- One-time commands or instructions ("stop the script", "continue where you left off")
- Acknowledgments or emotional reactions ("ok", "sounds good", "you're right", "sir")
- Transient UI/navigation states ("user is in the admin panel", "relay is attached")
- Ephemeral process status ("download at 50%", "daemon not running", "still syncing")
- Cron heartbeat outputs, NO_REPLY responses, compaction flush directives
- System routing metadata (message IDs, sender IDs, channel routing info)
- Generic small talk with no informational content
- Raw code snippets (capture the intent/decision, not the code itself)
- Information the user explicitly asks not to remember`;

const DEFAULT_CUSTOM_CATEGORIES: Record<string, string> = {
  identity:
    "Personal identity information: name, age, location, timezone, occupation, employer, education, demographics",
  preferences:
    "Explicitly stated likes, dislikes, preferences, opinions, and values across any domain",
  goals:
    "Current and future goals, aspirations, objectives, targets the user is working toward",
  projects:
    "Specific projects, initiatives, or endeavors the user is working on, including status and details",
  technical:
    "Technical skills, tools, tech stack, development environment, programming languages, frameworks",
  decisions:
    "Important decisions made, reasoning behind choices, strategy changes, and their outcomes",
  relationships:
    "People mentioned by the user: colleagues, family, friends, their roles and relevance",
  routines:
    "Daily habits, work patterns, schedules, productivity routines, health and wellness habits",
  life_events:
    "Significant life events, milestones, transitions, upcoming plans and changes",
  lessons:
    "Lessons learned, insights gained, mistakes acknowledged, changed opinions or beliefs",
  work:
    "Work-related context: job responsibilities, workplace dynamics, career progression, professional challenges",
  health:
    "Health-related information voluntarily shared: conditions, medications, fitness, wellness goals",
};

// ============================================================================
// Config Schema
// ============================================================================

const ALLOWED_KEYS = [
  "mode",
  "apiKey",
  "userId",
  "orgId",
  "projectId",
  "autoCapture",
  "autoRecall",
  "customInstructions",
  "customCategories",
  "customPrompt",
  "enableGraph",
  "searchThreshold",
  "topK",
  "oss",
];

function assertAllowedKeys(
  value: Record<string, unknown>,
  allowed: string[],
  label: string,
) {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length === 0) return;
  throw new Error(`${label} has unknown keys: ${unknown.join(", ")}`);
}

export const mem0ConfigSchema = {
  parse(value: unknown): Mem0Config {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("openclaw-mem0 config required");
    }
    const cfg = value as Record<string, unknown>;
    assertAllowedKeys(cfg, ALLOWED_KEYS, "openclaw-mem0 config");

    // Accept both "open-source" and legacy "oss" as open-source mode; everything else is platform
    const mode: Mem0Mode =
      cfg.mode === "oss" || cfg.mode === "open-source" ? "open-source" : "platform";

    // Platform mode requires apiKey
    if (mode === "platform") {
      if (typeof cfg.apiKey !== "string" || !cfg.apiKey) {
        throw new Error(
          "apiKey is required for platform mode (set mode: \"open-source\" for self-hosted)",
        );
      }
    }

    // Resolve env vars in oss config
    let ossConfig: Mem0Config["oss"];
    if (cfg.oss && typeof cfg.oss === "object" && !Array.isArray(cfg.oss)) {
      ossConfig = resolveEnvVarsDeep(
        cfg.oss as Record<string, unknown>,
      ) as unknown as Mem0Config["oss"];
    }

    return {
      mode,
      apiKey:
        typeof cfg.apiKey === "string" ? resolveEnvVars(cfg.apiKey) : undefined,
      userId:
        typeof cfg.userId === "string" && cfg.userId ? cfg.userId : "default",
      orgId: typeof cfg.orgId === "string" ? cfg.orgId : undefined,
      projectId: typeof cfg.projectId === "string" ? cfg.projectId : undefined,
      autoCapture: cfg.autoCapture !== false,
      autoRecall: cfg.autoRecall !== false,
      customInstructions:
        typeof cfg.customInstructions === "string"
          ? cfg.customInstructions
          : DEFAULT_CUSTOM_INSTRUCTIONS,
      customCategories:
        cfg.customCategories &&
          typeof cfg.customCategories === "object" &&
          !Array.isArray(cfg.customCategories)
          ? (cfg.customCategories as Record<string, string>)
          : DEFAULT_CUSTOM_CATEGORIES,
      customPrompt:
        typeof cfg.customPrompt === "string"
          ? cfg.customPrompt
          : DEFAULT_CUSTOM_INSTRUCTIONS,
      enableGraph: cfg.enableGraph === true,
      searchThreshold:
        typeof cfg.searchThreshold === "number" ? cfg.searchThreshold : 0.7,
      topK: typeof cfg.topK === "number" ? cfg.topK : 5,
      oss: ossConfig,
    };
  },
};

// ============================================================================
// Provider Factory
// ============================================================================

export function createProvider(
  cfg: Mem0Config,
  api: OpenClawPluginApi,
): Mem0Provider {
  if (cfg.mode === "open-source") {
    return new OSSProvider(cfg.oss, cfg.customPrompt, (p) =>
      api.resolvePath(p),
    );
  }

  return new PlatformProvider(cfg.apiKey!, cfg.orgId, cfg.projectId);
}

// ============================================================================
// Helpers
// ============================================================================

/** Convert Record<string, string> categories to the array format mem0ai expects */
function categoriesToArray(
  cats: Record<string, string>,
): Array<Record<string, string>> {
  return Object.entries(cats).map(([key, value]) => ({ [key]: value }));
}

// ============================================================================
// Message Filtering (pre-extraction noise removal)
// ============================================================================

/** Patterns that indicate an entire message is noise and should be dropped. */
const NOISE_MESSAGE_PATTERNS: RegExp[] = [
  /^(HEARTBEAT_OK|NO_REPLY)$/i,
  /^Current time:.*\d{4}/,
  /^Pre-compaction memory flush/i,
  /^(ok|yes|no|sir|sure|thanks|done|good|nice|cool|got it|it's on|continue)$/i,
  /^System: \[.*\] (Slack message edited|Gateway restart|Exec (failed|completed))/,
  /^System: \[.*\] ⚠️ Post-Compaction Audit:/,
];

/** Content fragments that should be stripped from otherwise-valid messages. */
const NOISE_CONTENT_PATTERNS: Array<{ pattern: RegExp; replacement: string }> = [
  { pattern: /Conversation info \(untrusted metadata\):\s*```json\s*\{[\s\S]*?\}\s*```/g, replacement: "" },
  { pattern: /\[media attached:.*?\]/g, replacement: "" },
  { pattern: /To send an image back, prefer the message tool[\s\S]*?Keep caption in the text body\./g, replacement: "" },
  { pattern: /System: \[\d{4}-\d{2}-\d{2}.*?\] ⚠️ Post-Compaction Audit:[\s\S]*?after memory compaction\./g, replacement: "" },
  { pattern: /Replied message \(untrusted, for context\):\s*```json[\s\S]*?```/g, replacement: "" },
];

const MAX_MESSAGE_LENGTH = 2000;

/**
 * Patterns indicating an assistant message is a generic acknowledgment with
 * no extractable facts. These are produced when the agent receives a
 * transcript dump or forwarded message and responds with a boilerplate reply.
 */
const GENERIC_ASSISTANT_PATTERNS: RegExp[] = [
  /^(I see you'?ve shared|Thanks for sharing|Got it[.!]?\s*(I see|Let me|How can)|I understand[.!]?\s*(How can|Is there|Would you))/i,
  /^(How can I help|Is there anything|Would you like me to|Let me know (if|how|what))/i,
  /^(I('?ll| will) (help|assist|look into|review|take a look))/i,
  /^(Sure[.!]?\s*(How|What|Is)|Understood[.!]?\s*(How|What|Is))/i,
  /^(That('?s| is) (noted|understood|clear))/i,
];

/**
 * Check whether a message's content is entirely noise (cron heartbeats,
 * single-word acknowledgments, system routing metadata, etc.).
 */
export function isNoiseMessage(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) return true;
  return NOISE_MESSAGE_PATTERNS.some((p) => p.test(trimmed));
}

/**
 * Check whether an assistant message is a generic acknowledgment with no
 * extractable facts (e.g. "I see you've shared an update. How can I help?").
 * Only applies to short assistant messages — longer responses likely contain
 * substantive content even if they start with a generic opener.
 */
export function isGenericAssistantMessage(content: string): boolean {
  const trimmed = content.trim();
  // Only flag short messages — longer ones likely have substance after the opener
  if (trimmed.length > 300) return false;
  return GENERIC_ASSISTANT_PATTERNS.some((p) => p.test(trimmed));
}

/**
 * Remove embedded noise fragments (routing metadata, media boilerplate,
 * compaction audit blocks) from a message while preserving the useful content.
 */
export function stripNoiseFromContent(content: string): string {
  let cleaned = content;
  for (const { pattern, replacement } of NOISE_CONTENT_PATTERNS) {
    cleaned = cleaned.replace(pattern, replacement);
  }
  // Collapse excessive whitespace left behind after stripping
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n").trim();
  return cleaned;
}

/**
 * Truncate a message to `MAX_MESSAGE_LENGTH` characters, preserving the
 * opening (which typically contains the summary/conclusion) and appending
 * a truncation marker so the extraction model knows content was cut.
 */
function truncateMessage(content: string): string {
  if (content.length <= MAX_MESSAGE_LENGTH) return content;
  return content.slice(0, MAX_MESSAGE_LENGTH) + "\n[...truncated]";
}

/**
 * Full pre-extraction pipeline: drop noise messages, strip noise fragments,
 * and truncate remaining messages to a reasonable length.
 */
export function filterMessagesForExtraction(
  messages: Array<{ role: string; content: string }>,
): Array<{ role: string; content: string }> {
  const filtered: Array<{ role: string; content: string }> = [];
  for (const msg of messages) {
    if (isNoiseMessage(msg.content)) continue;
    // Drop generic assistant acknowledgments that contain no facts
    if (msg.role === "assistant" && isGenericAssistantMessage(msg.content)) continue;
    const cleaned = stripNoiseFromContent(msg.content);
    if (!cleaned) continue;
    filtered.push({ role: msg.role, content: truncateMessage(cleaned) });
  }
  return filtered;
}

/**
 * Compute word-level Jaccard similarity between two strings.
 * Used to detect near-duplicate recalled memories.
 */
function wordJaccard(a: string, b: string): number {
  const wordsA = new Set(a.toLowerCase().split(/\s+/));
  const wordsB = new Set(b.toLowerCase().split(/\s+/));
  let intersection = 0;
  for (const w of wordsA) {
    if (wordsB.has(w)) intersection++;
  }
  const union = wordsA.size + wordsB.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

/**
 * Remove near-duplicate memories from a list. When two memories have
 * >80% word overlap, only the higher-scoring one is kept.
 * Sorts by score descending first so the highest-scored variant wins.
 */
export function deduplicateByContent(memories: MemoryItem[]): MemoryItem[] {
  if (memories.length <= 1) return memories;
  // Sort descending by score so the highest-scored item is encountered first
  const sorted = [...memories].sort(
    (a, b) => (b.score ?? 0) - (a.score ?? 0),
  );
  const kept: MemoryItem[] = [];
  for (const mem of sorted) {
    const isDuplicate = kept.some(
      (existing) => wordJaccard(existing.memory, mem.memory) > 0.8,
    );
    if (!isDuplicate) kept.push(mem);
  }
  return kept;
}

// ============================================================================
// Per-agent isolation helpers (exported for testability)
// ============================================================================

/**
 * Parse an agent ID from a session key following the pattern `agent:<agentId>:<uuid>`.
 * Returns undefined for non-agent sessions, the "main" sentinel, or malformed keys.
 */
export function extractAgentId(sessionKey: string | undefined): string | undefined {
  if (!sessionKey) return undefined;
  const match = sessionKey.match(/^agent:([^:]+):/);
  const agentId = match?.[1];
  // "main" is the primary session — fall back to configured userId
  if (!agentId || agentId === "main") return undefined;
  return agentId;
}

/**
 * Derive the effective user_id from a session key, namespacing per-agent.
 * Falls back to baseUserId when the session is not agent-scoped.
 */
export function effectiveUserId(baseUserId: string, sessionKey?: string): string {
  const agentId = extractAgentId(sessionKey);
  return agentId ? `${baseUserId}:agent:${agentId}` : baseUserId;
}

/** Build a user_id for an explicit agentId (e.g. from tool params). */
export function agentUserId(baseUserId: string, agentId: string): string {
  return `${baseUserId}:agent:${agentId}`;
}

/**
 * Resolve user_id with priority: explicit agentId > explicit userId > session-derived > configured.
 */
export function resolveUserId(
  baseUserId: string,
  opts: { agentId?: string; userId?: string },
  currentSessionId?: string,
): string {
  if (opts.agentId) return agentUserId(baseUserId, opts.agentId);
  if (opts.userId) return opts.userId;
  return effectiveUserId(baseUserId, currentSessionId);
}

// ============================================================================
// Plugin Definition
// ============================================================================

const memoryPlugin = {
  id: "openclaw-mem0",
  name: "Memory (Mem0)",
  description:
    "Mem0 memory backend — Mem0 platform or self-hosted open-source",
  kind: "memory" as const,
  configSchema: mem0ConfigSchema,

  register(api: OpenClawPluginApi) {
    const cfg = mem0ConfigSchema.parse(api.pluginConfig);
    const provider = createProvider(cfg, api);

    // Track current session ID for tool-level session scoping
    let currentSessionId: string | undefined;

    // ========================================================================
    // Per-agent isolation helpers (thin wrappers around exported functions)
    // ========================================================================
    const _effectiveUserId = (sessionKey?: string) =>
      effectiveUserId(cfg.userId, sessionKey);
    const _agentUserId = (id: string) => agentUserId(cfg.userId, id);
    const _resolveUserId = (opts: { agentId?: string; userId?: string }) =>
      resolveUserId(cfg.userId, opts, currentSessionId);

    api.logger.info(
      `openclaw-mem0: registered (mode: ${cfg.mode}, user: ${cfg.userId}, graph: ${cfg.enableGraph}, autoRecall: ${cfg.autoRecall}, autoCapture: ${cfg.autoCapture})`,
    );

    // Helper: build add options
    function buildAddOptions(userIdOverride?: string, runId?: string, sessionKey?: string): AddOptions {
      const opts: AddOptions = {
        user_id: userIdOverride || _effectiveUserId(sessionKey),
        source: "OPENCLAW",
      };
      if (runId) opts.run_id = runId;
      if (cfg.mode === "platform") {
        opts.custom_instructions = cfg.customInstructions;
        opts.custom_categories = categoriesToArray(cfg.customCategories);
        opts.enable_graph = cfg.enableGraph;
        opts.output_format = "v1.1";
      }
      return opts;
    }

    // Helper: build search options
    function buildSearchOptions(
      userIdOverride?: string,
      limit?: number,
      runId?: string,
      sessionKey?: string,
    ): SearchOptions {
      const opts: SearchOptions = {
        user_id: userIdOverride || _effectiveUserId(sessionKey),
        top_k: limit ?? cfg.topK,
        limit: limit ?? cfg.topK,
        threshold: cfg.searchThreshold,
        keyword_search: true,
        reranking: true,
        source: "OPENCLAW",
      };
      if (runId) opts.run_id = runId;
      return opts;
    }

    // ========================================================================
    // Tools
    // ========================================================================

    api.registerTool(
      {
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
              description:
                "User ID to scope search (default: configured userId)",
            }),
          ),
          agentId: Type.Optional(
            Type.String({
              description:
                "Agent ID to search memories for a specific agent (e.g. \"researcher\"). Overrides userId.",
            }),
          ),
          scope: Type.Optional(
            Type.Union([
              Type.Literal("session"),
              Type.Literal("long-term"),
              Type.Literal("all"),
            ], {
              description:
                'Memory scope: "session" (current session only), "long-term" (user-scoped only), or "all" (both). Default: "all"',
            }),
          ),
        }),
        async execute(_toolCallId, params) {
          const { query, limit, userId, agentId, scope = "all" } = params as {
            query: string;
            limit?: number;
            userId?: string;
            agentId?: string;
            scope?: "session" | "long-term" | "all";
          };

          try {
            let results: MemoryItem[] = [];
            const uid = _resolveUserId({ agentId, userId });

            if (scope === "session") {
              if (currentSessionId) {
                results = await provider.search(
                  query,
                  buildSearchOptions(uid, limit, currentSessionId),
                );
              }
            } else if (scope === "long-term") {
              results = await provider.search(
                query,
                buildSearchOptions(uid, limit),
              );
            } else {
              // "all" — search both scopes and combine
              const longTermResults = await provider.search(
                query,
                buildSearchOptions(uid, limit),
              );
              let sessionResults: MemoryItem[] = [];
              if (currentSessionId) {
                sessionResults = await provider.search(
                  query,
                  buildSearchOptions(uid, limit, currentSessionId),
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
                content: [
                  { type: "text", text: "No relevant memories found." },
                ],
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
      },
      { name: "memory_search" },
    );

    api.registerTool(
      {
        name: "memory_store",
        label: "Memory Store",
        description:
          "Save important information in long-term memory via Mem0. Use for preferences, facts, decisions, and anything worth remembering.",
        parameters: Type.Object({
          text: Type.String({ description: "Information to remember" }),
          userId: Type.Optional(
            Type.String({
              description: "User ID to scope this memory",
            }),
          ),
          agentId: Type.Optional(
            Type.String({
              description:
                "Agent ID to store memory under a specific agent's namespace (e.g. \"researcher\"). Overrides userId.",
            }),
          ),
          metadata: Type.Optional(
            Type.Record(Type.String(), Type.Unknown(), {
              description: "Optional metadata to attach to this memory",
            }),
          ),
          longTerm: Type.Optional(
            Type.Boolean({
              description:
                "Store as long-term (user-scoped) memory. Default: true. Set to false for session-scoped memory.",
            }),
          ),
        }),
        async execute(_toolCallId, params) {
          const { text, userId, agentId, longTerm = true } = params as {
            text: string;
            userId?: string;
            agentId?: string;
            metadata?: Record<string, unknown>;
            longTerm?: boolean;
          };

          try {
            const uid = _resolveUserId({ agentId, userId });
            const runId = !longTerm && currentSessionId ? currentSessionId : undefined;

            // Pre-check for near-duplicates so the extraction model has
            // context about existing memories and can UPDATE rather than ADD
            const preview = text.slice(0, 200);
            const dedupOpts = buildSearchOptions(uid, 3);
            dedupOpts.threshold = 0.85;
            const existing = await provider.search(preview, dedupOpts);
            if (existing.length > 0) {
              api.logger.info(
                `openclaw-mem0: found ${existing.length} similar existing memories — mem0 may update instead of add`,
              );
            }

            const result = await provider.add(
              [{ role: "user", content: text }],
              buildAddOptions(uid, runId, currentSessionId),
            );

            const added =
              result.results?.filter((r) => r.event === "ADD") ?? [];
            const updated =
              result.results?.filter((r) => r.event === "UPDATE") ?? [];

            const summary = [];
            if (added.length > 0)
              summary.push(
                `${added.length} new memor${added.length === 1 ? "y" : "ies"} added`,
              );
            if (updated.length > 0)
              summary.push(
                `${updated.length} memor${updated.length === 1 ? "y" : "ies"} updated`,
              );
            if (summary.length === 0)
              summary.push("No new memories extracted");

            return {
              content: [
                {
                  type: "text",
                  text: `Stored: ${summary.join(", ")}. ${result.results?.map((r) => `[${r.event}] ${r.memory}`).join("; ") ?? ""}`,
                },
              ],
              details: {
                action: "stored",
                results: result.results,
              },
            };
          } catch (err) {
            return {
              content: [
                {
                  type: "text",
                  text: `Memory store failed: ${String(err)}`,
                },
              ],
              details: { error: String(err) },
            };
          }
        },
      },
      { name: "memory_store" },
    );

    api.registerTool(
      {
        name: "memory_get",
        label: "Memory Get",
        description: "Retrieve a specific memory by its ID from Mem0.",
        parameters: Type.Object({
          memoryId: Type.String({ description: "The memory ID to retrieve" }),
        }),
        async execute(_toolCallId, params) {
          const { memoryId } = params as { memoryId: string };

          try {
            const memory = await provider.get(memoryId);

            return {
              content: [
                {
                  type: "text",
                  text: `Memory ${memory.id}:\n${memory.memory}\n\nCreated: ${memory.created_at ?? "unknown"}\nUpdated: ${memory.updated_at ?? "unknown"}`,
                },
              ],
              details: { memory },
            };
          } catch (err) {
            return {
              content: [
                {
                  type: "text",
                  text: `Memory get failed: ${String(err)}`,
                },
              ],
              details: { error: String(err) },
            };
          }
        },
      },
      { name: "memory_get" },
    );

    api.registerTool(
      {
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
                "Agent ID to list memories for a specific agent (e.g. \"researcher\"). Overrides userId.",
            }),
          ),
          scope: Type.Optional(
            Type.Union([
              Type.Literal("session"),
              Type.Literal("long-term"),
              Type.Literal("all"),
            ], {
              description:
                'Memory scope: "session" (current session only), "long-term" (user-scoped only), or "all" (both). Default: "all"',
            }),
          ),
        }),
        async execute(_toolCallId, params) {
          const { userId, agentId, scope = "all" } = params as { userId?: string; agentId?: string; scope?: "session" | "long-term" | "all" };

          try {
            let memories: MemoryItem[] = [];
            const uid = _resolveUserId({ agentId, userId });

            if (scope === "session") {
              if (currentSessionId) {
                memories = await provider.getAll({
                  user_id: uid,
                  run_id: currentSessionId,
                  source: "OPENCLAW",
                });
              }
            } else if (scope === "long-term") {
              memories = await provider.getAll({ user_id: uid, source: "OPENCLAW" });
            } else {
              // "all" — combine both scopes
              const longTerm = await provider.getAll({ user_id: uid, source: "OPENCLAW" });
              let session: MemoryItem[] = [];
              if (currentSessionId) {
                session = await provider.getAll({
                  user_id: uid,
                  run_id: currentSessionId,
                  source: "OPENCLAW",
                });
              }
              const seen = new Set(longTerm.map((r) => r.id));
              memories = [
                ...longTerm,
                ...session.filter((r) => !seen.has(r.id)),
              ];
            }

            if (!memories || memories.length === 0) {
              return {
                content: [
                  { type: "text", text: "No memories stored yet." },
                ],
                details: { count: 0 },
              };
            }

            const text = memories
              .map(
                (r, i) =>
                  `${i + 1}. ${r.memory} (id: ${r.id})`,
              )
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
      },
      { name: "memory_list" },
    );

    api.registerTool(
      {
        name: "memory_forget",
        label: "Memory Forget",
        description:
          "Delete memories from Mem0. Provide a specific memoryId to delete directly, or a query to search and delete matching memories. Supports agent-scoped deletion. GDPR-compliant.",
        parameters: Type.Object({
          query: Type.Optional(
            Type.String({
              description: "Search query to find memory to delete",
            }),
          ),
          memoryId: Type.Optional(
            Type.String({ description: "Specific memory ID to delete" }),
          ),
          agentId: Type.Optional(
            Type.String({
              description:
                "Agent ID to scope deletion to a specific agent's memories (e.g. \"researcher\").",
            }),
          ),
        }),
        async execute(_toolCallId, params) {
          const { query, memoryId, agentId } = params as {
            query?: string;
            memoryId?: string;
            agentId?: string;
          };

          try {
            if (memoryId) {
              await provider.delete(memoryId);
              return {
                content: [
                  { type: "text", text: `Memory ${memoryId} forgotten.` },
                ],
                details: { action: "deleted", id: memoryId },
              };
            }

            if (query) {
              const uid = _resolveUserId({ agentId });
              const results = await provider.search(
                query,
                buildSearchOptions(uid, 5),
              );

              if (!results || results.length === 0) {
                return {
                  content: [
                    { type: "text", text: "No matching memories found." },
                  ],
                  details: { found: 0 },
                };
              }

              // If single high-confidence match, delete directly
              if (
                results.length === 1 ||
                (results[0].score ?? 0) > 0.9
              ) {
                await provider.delete(results[0].id);
                return {
                  content: [
                    {
                      type: "text",
                      text: `Forgotten: "${results[0].memory}"`,
                    },
                  ],
                  details: { action: "deleted", id: results[0].id },
                };
              }

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
                    text: `Found ${results.length} candidates. Specify memoryId to delete:\n${list}`,
                  },
                ],
                details: { action: "candidates", candidates },
              };
            }

            return {
              content: [
                { type: "text", text: "Provide a query or memoryId." },
              ],
              details: { error: "missing_param" },
            };
          } catch (err) {
            return {
              content: [
                {
                  type: "text",
                  text: `Memory forget failed: ${String(err)}`,
                },
              ],
              details: { error: String(err) },
            };
          }
        },
      },
      { name: "memory_forget" },
    );

    // ========================================================================
    // CLI Commands
    // ========================================================================

    api.registerCli(
      ({ program }) => {
        const mem0 = program
          .command("mem0")
          .description("Mem0 memory plugin commands");

        mem0
          .command("search")
          .description("Search memories in Mem0")
          .argument("<query>", "Search query")
          .option("--limit <n>", "Max results", String(cfg.topK))
          .option("--scope <scope>", 'Memory scope: "session", "long-term", or "all"', "all")
          .option("--agent <agentId>", "Search a specific agent's memory namespace")
          .action(async (query: string, opts: { limit: string; scope: string; agent?: string }) => {
            try {
              const limit = parseInt(opts.limit, 10);
              const scope = opts.scope as "session" | "long-term" | "all";
              const uid = opts.agent ? _agentUserId(opts.agent) : _effectiveUserId(currentSessionId);

              let allResults: MemoryItem[] = [];

              if (scope === "session" || scope === "all") {
                if (currentSessionId) {
                  const sessionResults = await provider.search(
                    query,
                    buildSearchOptions(uid, limit, currentSessionId),
                  );
                  if (sessionResults?.length) {
                    allResults.push(...sessionResults.map((r) => ({ ...r, _scope: "session" as const })));
                  }
                } else if (scope === "session") {
                  console.log("No active session ID available for session-scoped search.");
                  return;
                }
              }

              if (scope === "long-term" || scope === "all") {
                const longTermResults = await provider.search(
                  query,
                  buildSearchOptions(uid, limit),
                );
                if (longTermResults?.length) {
                  allResults.push(...longTermResults.map((r) => ({ ...r, _scope: "long-term" as const })));
                }
              }

              // Deduplicate by ID when searching "all"
              if (scope === "all") {
                const seen = new Set<string>();
                allResults = allResults.filter((r) => {
                  if (seen.has(r.id)) return false;
                  seen.add(r.id);
                  return true;
                });
              }

              if (!allResults.length) {
                console.log("No memories found.");
                return;
              }

              const output = allResults.map((r) => ({
                id: r.id,
                memory: r.memory,
                score: r.score,
                scope: (r as any)._scope,
                categories: r.categories,
                created_at: r.created_at,
              }));
              console.log(JSON.stringify(output, null, 2));
            } catch (err) {
              console.error(`Search failed: ${String(err)}`);
            }
          });

        mem0
          .command("stats")
          .description("Show memory statistics from Mem0")
          .option("--agent <agentId>", "Show stats for a specific agent")
          .action(async (opts: { agent?: string }) => {
            try {
              const uid = opts.agent ? _agentUserId(opts.agent) : cfg.userId;
              const memories = await provider.getAll({
                user_id: uid,
                source: "OPENCLAW",
              });
              console.log(`Mode: ${cfg.mode}`);
              console.log(`User: ${uid}${opts.agent ? ` (agent: ${opts.agent})` : ""}`);
              console.log(
                `Total memories: ${Array.isArray(memories) ? memories.length : "unknown"}`,
              );
              console.log(`Graph enabled: ${cfg.enableGraph}`);
              console.log(
                `Auto-recall: ${cfg.autoRecall}, Auto-capture: ${cfg.autoCapture}`,
              );
            } catch (err) {
              console.error(`Stats failed: ${String(err)}`);
            }
          });
      },
      { commands: ["mem0"] },
    );

    // ========================================================================
    // Lifecycle Hooks
    // ========================================================================

    // Auto-recall: inject relevant memories before agent starts
    if (cfg.autoRecall) {
      api.on("before_agent_start", async (event, ctx) => {
        if (!event.prompt || event.prompt.length < 5) return;

        // Track session ID and detect session boundary
        const sessionId = (ctx as any)?.sessionKey ?? undefined;
        const isNewSession = sessionId && sessionId !== currentSessionId;
        if (sessionId) currentSessionId = sessionId;

        try {
          // Use a larger candidate pool for recall, then filter down
          const recallTopK = Math.max((cfg.topK ?? 5) * 2, 10);

          // Search long-term memories (user-scoped, isolated per agent)
          let longTermResults = await provider.search(
            event.prompt,
            buildSearchOptions(undefined, recallTopK, undefined, sessionId),
          );

          // Client-side threshold filter — ensures low-relevance results
          // are dropped even if the API doesn't honor the threshold
          longTermResults = longTermResults.filter(
            (r) => (r.score ?? 0) >= cfg.searchThreshold,
          );

          // For short/generic prompts or new sessions, broaden recall
          // with a general query to avoid cold-start blindness.
          // Use a lower threshold (0.5) since the generic query is
          // intentionally broad and strict thresholds defeat the purpose.
          if (event.prompt.length < 100 || isNewSession) {
            const broadOpts = buildSearchOptions(undefined, 5, undefined, sessionId);
            broadOpts.threshold = 0.5;
            const broadResults = await provider.search(
              "recent decisions, preferences, active projects, and configuration",
              broadOpts,
            );
            const existingIds = new Set(longTermResults.map((r) => r.id));
            for (const r of broadResults) {
              if (!existingIds.has(r.id)) {
                longTermResults.push(r);
              }
            }
          }

          // Remove near-duplicate recalled memories (>80% word overlap)
          longTermResults = deduplicateByContent(longTermResults);

          // Cap at configured topK after filtering and dedup
          longTermResults = longTermResults.slice(0, cfg.topK);

          // Search session memories (session-scoped) if we have a session ID
          let sessionResults: MemoryItem[] = [];
          if (currentSessionId) {
            sessionResults = await provider.search(
              event.prompt,
              buildSearchOptions(undefined, undefined, currentSessionId, sessionId),
            );
            sessionResults = sessionResults.filter(
              (r) => (r.score ?? 0) >= cfg.searchThreshold,
            );
          }

          // Deduplicate session results against long-term
          const longTermIds = new Set(longTermResults.map((r) => r.id));
          const uniqueSessionResults = sessionResults.filter(
            (r) => !longTermIds.has(r.id),
          );

          if (longTermResults.length === 0 && uniqueSessionResults.length === 0) return;

          // Build context with clear labels
          let memoryContext = "";
          if (longTermResults.length > 0) {
            memoryContext += longTermResults
              .map(
                (r) =>
                  `- ${r.memory}${r.categories?.length ? ` [${r.categories.join(", ")}]` : ""}`,
              )
              .join("\n");
          }
          if (uniqueSessionResults.length > 0) {
            if (memoryContext) memoryContext += "\n";
            memoryContext += "\nSession memories:\n";
            memoryContext += uniqueSessionResults
              .map((r) => `- ${r.memory}`)
              .join("\n");
          }

          const totalCount = longTermResults.length + uniqueSessionResults.length;
          api.logger.info(
            `openclaw-mem0: injecting ${totalCount} memories into context (${longTermResults.length} long-term, ${uniqueSessionResults.length} session)`,
          );

          return {
            prependContext: `<relevant-memories>\nThe following memories may be relevant to this conversation:\n${memoryContext}\n</relevant-memories>`,
          };
        } catch (err) {
          api.logger.warn(`openclaw-mem0: recall failed: ${String(err)}`);
        }
      });
    }

    // Auto-capture: store conversation context after agent ends
    if (cfg.autoCapture) {
      api.on("agent_end", async (event, ctx) => {
        if (!event.success || !event.messages || event.messages.length === 0) {
          return;
        }

        // Track session ID
        const sessionId = (ctx as any)?.sessionKey ?? undefined;
        if (sessionId) currentSessionId = sessionId;

        try {
          // Patterns indicating an assistant message contains a summary of
          // completed work — these are high-value for extraction and should
          // be included even if they fall outside the recent-message window.
          const SUMMARY_PATTERNS = [
            /## What I (Accomplished|Built|Updated)/i,
            /✅\s*(Done|Complete|All done)/i,
            /Here's (what I updated|the recap|a summary)/i,
            /### Changes Made/i,
            /Implementation Status/i,
            /All locked in\. Quick summary/i,
          ];

          // First pass: extract all messages into a typed array
          const allParsed: Array<{
            role: string;
            content: string;
            index: number;
            isSummary: boolean;
          }> = [];

          for (let i = 0; i < event.messages.length; i++) {
            const msg = event.messages[i];
            if (!msg || typeof msg !== "object") continue;
            const msgObj = msg as Record<string, unknown>;

            const role = msgObj.role;
            if (role !== "user" && role !== "assistant") continue;

            let textContent = "";
            const content = msgObj.content;

            if (typeof content === "string") {
              textContent = content;
            } else if (Array.isArray(content)) {
              for (const block of content) {
                if (
                  block &&
                  typeof block === "object" &&
                  "text" in block &&
                  typeof (block as Record<string, unknown>).text === "string"
                ) {
                  textContent +=
                    (textContent ? "\n" : "") +
                    ((block as Record<string, unknown>).text as string);
                }
              }
            }

            if (!textContent) continue;
            // Strip injected memory context, keep the actual user text
            if (textContent.includes("<relevant-memories>")) {
              textContent = textContent.replace(/<relevant-memories>[\s\S]*?<\/relevant-memories>\s*/g, "").trim();
              if (!textContent) continue;
            }

            const isSummary =
              role === "assistant" &&
              SUMMARY_PATTERNS.some((p) => p.test(textContent));

            allParsed.push({
              role: role as string,
              content: textContent,
              index: i,
              isSummary,
            });
          }

          if (allParsed.length === 0) return;

          // Select messages: last 20 + any earlier summary messages,
          // sorted by original index to preserve chronological order.
          const recentWindow = 20;
          const recentCutoff = allParsed.length - recentWindow;

          const candidates: typeof allParsed = [];

          // Include summary messages from anywhere in the conversation
          for (const msg of allParsed) {
            if (msg.isSummary && msg.index < recentCutoff) {
              candidates.push(msg);
            }
          }

          // Include recent messages
          const seenIndices = new Set(candidates.map((m) => m.index));
          for (const msg of allParsed) {
            if (msg.index >= recentCutoff && !seenIndices.has(msg.index)) {
              candidates.push(msg);
            }
          }

          // Sort by original position so the extraction model sees
          // messages in the order they actually occurred
          candidates.sort((a, b) => a.index - b.index);

          const selected = candidates.map((m) => ({
            role: m.role,
            content: m.content,
          }));

          // Apply noise filtering pipeline: drop noise, strip fragments, truncate
          const formattedMessages = filterMessagesForExtraction(selected);

          if (formattedMessages.length === 0) return;

          // Inject a timestamp preamble so the extraction model can anchor
          // time-sensitive facts to a concrete date
          const timestamp = new Date().toISOString().split("T")[0];
          formattedMessages.unshift({
            role: "system",
            content: `Current date: ${timestamp}. Extract durable facts from this conversation. Include this date when storing time-sensitive information.`,
          });

          const addOpts = buildAddOptions(undefined, currentSessionId, sessionId);
          const result = await provider.add(
            formattedMessages,
            addOpts,
          );

          const capturedCount = result.results?.length ?? 0;
          if (capturedCount > 0) {
            api.logger.info(
              `openclaw-mem0: auto-captured ${capturedCount} memories`,
            );
          }
        } catch (err) {
          api.logger.warn(`openclaw-mem0: capture failed: ${String(err)}`);
        }
      });
    }

    // ========================================================================
    // Service
    // ========================================================================

    api.registerService({
      id: "openclaw-mem0",
      start: () => {
        api.logger.info(
          `openclaw-mem0: initialized (mode: ${cfg.mode}, user: ${cfg.userId}, autoRecall: ${cfg.autoRecall}, autoCapture: ${cfg.autoCapture})`,
        );
      },
      stop: () => {
        api.logger.info("openclaw-mem0: stopped");
      },
    });
  },
};

export default memoryPlugin;
