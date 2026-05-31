/**
 * Skill Loader — reads skill markdown files, merges domain overlays,
 * injects user config, and produces the final injectable prompt string.
 */

import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { SkillsConfig, CategoryConfig } from "./types.ts";
import { readText, exists } from "./fs-safe.ts";

// ============================================================================
// Defaults
// ============================================================================

const DEFAULT_CATEGORIES: Record<string, CategoryConfig> = {
  configuration: { importance: 0.95, ttl: null },
  rule: { importance: 0.9, ttl: null },
  identity: { importance: 0.95, ttl: null, immutable: true },
  preference: { importance: 0.85, ttl: null },
  decision: { importance: 0.8, ttl: null },
  technical: { importance: 0.8, ttl: null },
  relationship: { importance: 0.75, ttl: null },
  project: { importance: 0.75, ttl: "90d" },
  operational: { importance: 0.6, ttl: "7d" },
};

const DEFAULT_CREDENTIAL_PATTERNS = [
  "sk-",
  "m0-",
  "ghp_",
  "AKIA",
  "ak_",
  "Bearer ",
  "bot\\d+:AA",
  "password=",
  "token=",
  "secret=",
];

// ============================================================================
// Skill File Reader
// ============================================================================

interface SkillFrontmatter {
  name: string;
  description?: string;
  "user-invocable"?: boolean;
  metadata?: string;
  applies_to?: string;
}

interface ParsedSkill {
  frontmatter: SkillFrontmatter;
  body: string;
}

function parseSkillFile(content: string): ParsedSkill {
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!fmMatch) {
    return {
      frontmatter: { name: "unknown" },
      body: content,
    };
  }

  const fmBlock = fmMatch[1];
  const body = fmMatch[2].trim();

  // Simple YAML-like parsing (no dependency needed)
  const fm: Record<string, any> = {};
  for (const line of fmBlock.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim();
    let value: any = line.slice(colonIdx + 1).trim();
    if (value === "false") value = false;
    else if (value === "true") value = true;
    fm[key] = value;
  }

  return {
    frontmatter: fm as SkillFrontmatter,
    body,
  };
}

// ============================================================================
// Skill Loader
// ============================================================================

// Resolve skills directory with multiple fallback strategies.
// OpenClaw may load the plugin via jiti or custom loaders that break
// import.meta.url, so we try several paths.
function resolveSkillsDir(): string {
  const candidates: string[] = [];

  // Strategy 1: import.meta.url (works in native ESM)
  try {
    const metaDir = path.dirname(fileURLToPath(import.meta.url));
    candidates.push(path.join(metaDir, "skills"));
    candidates.push(path.join(metaDir, "..", "skills"));
  } catch {
    /* import.meta.url may not be available */
  }

  // Strategy 2: __dirname (works in CJS / jiti)
  if (typeof __dirname !== "undefined") {
    candidates.push(path.join(__dirname, "skills"));
    candidates.push(path.join(__dirname, "..", "skills"));
  }

  // Validate: must contain the expected subdirectory structure
  for (const dir of candidates) {
    if (exists(path.join(dir, "memory-triage", "SKILL.md"))) {
      return dir;
    }
  }

  return candidates[0] ?? "skills"; // Will fail gracefully in readSkillFile
}

const SKILLS_DIR = resolveSkillsDir();
const RESOLVED_SKILLS_DIR = path.resolve(SKILLS_DIR);

/**
 * Resolve path segments under SKILLS_DIR and verify the result doesn't escape.
 * Returns null if the resolved path is outside the skills directory (path traversal).
 * Note: path.resolve follows symlinks lexically; the skills directory is
 * package-owned so symlink escape is not a practical concern.
 */
export function safePath(...segments: string[]): string | null {
  const resolved = path.resolve(SKILLS_DIR, ...segments);
  if (
    resolved !== RESOLVED_SKILLS_DIR &&
    !resolved.startsWith(RESOLVED_SKILLS_DIR + path.sep)
  ) {
    return null;
  }
  return resolved;
}

function readSkillFile(skillName: string): string | null {
  const filePath = safePath(skillName, "SKILL.md");
  if (!filePath) return null;
  try {
    return readText(filePath);
  } catch {
    return null;
  }
}

/**
 * Read a domain overlay, scoped to a specific skill.
 * Domain overlays live inside the skill directory: <skill>/domains/<domain>.md
 * The `applies_to` frontmatter field is checked for backward compatibility.
 */
function readDomainOverlay(domain: string, targetSkill: string): string | null {
  const filePath = safePath(targetSkill, "domains", `${domain}.md`);
  if (!filePath) return null;
  try {
    const content = readText(filePath);
    const parsed = parseSkillFile(content);
    // Check applies_to for backward compat (skip if targeting a different skill)
    const appliesTo = parsed.frontmatter.applies_to;
    if (appliesTo && appliesTo !== targetSkill) {
      return null;
    }
    return parsed.body;
  } catch {
    return null;
  }
}

// ============================================================================
// Config Injection — render user-configured knobs into prompt text
// ============================================================================

function renderCategoriesBlock(
  categories: Record<string, CategoryConfig>,
): string {
  const lines: string[] = [
    "\n## Active Category Configuration (overrides defaults above)\n",
  ];
  for (const [name, cat] of Object.entries(categories)) {
    const ttlLabel = cat.ttl ? `expires: ${cat.ttl}` : "permanent";
    const immLabel = cat.immutable ? ", immutable" : "";
    lines.push(
      `- **${name.toUpperCase()}** (importance: ${cat.importance} | ${ttlLabel}${immLabel})`,
    );
  }
  return lines.join("\n");
}

function renderTriageKnobs(config: SkillsConfig): string {
  const lines: string[] = [];

  if (config.triage?.importanceThreshold !== undefined) {
    lines.push(
      `- Only store facts with importance >= ${config.triage.importanceThreshold}`,
    );
  }

  const patterns = resolveCredentialPatterns(config);
  lines.push(`- Credential patterns to scan: ${patterns.map((p) => `\`${p}\``).join(", ")}`);

  if (lines.length === 0) return "";
  return "\n## Active Configuration Overrides\n\n" + lines.join("\n");
}

// ============================================================================
// TTL Helpers
// ============================================================================

/** Convert TTL string like "7d", "90d" to ISO date from today */
export function ttlToExpirationDate(ttl: string | null): string | null {
  if (!ttl) return null;
  const match = ttl.match(/^(\d+)d$/);
  if (!match) return null;
  const days = parseInt(match[1], 10);
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().split("T")[0]; // YYYY-MM-DD
}

// ============================================================================
// Public API
// ============================================================================

export interface LoadedSkill {
  name: string;
  prompt: string;
  frontmatter: SkillFrontmatter;
}

/**
 * Load a skill by name, merge domain overlays and user config,
 * and return the final injectable prompt string.
 */
export function loadSkill(
  skillName: string,
  config: SkillsConfig = {},
): LoadedSkill | null {
  const raw = readSkillFile(skillName);
  if (!raw) return null;

  const parsed = parseSkillFile(raw);
  const parts: string[] = [parsed.body];

  // Domain overlays only apply to the skill they target (checked via applies_to)
  if (config.domain) {
    const overlay = readDomainOverlay(config.domain, skillName);
    if (overlay) {
      parts.push("\n" + overlay);
    }
  }

  // Inject user-configured categories into triage skill prompt
  if (skillName === "memory-triage" && config.categories) {
    const mergedCats = resolveCategories(config);
    parts.push(renderCategoriesBlock(mergedCats));
  }

  // Inject triage knobs (importanceThreshold, credentialPatterns)
  if (skillName === "memory-triage" || skillName === "memory-dream") {
    const knobs = renderTriageKnobs(config);
    if (knobs) parts.push(knobs);
  }

  // Append user custom rules (triage-only — extraction rules don't apply to recall/dream)
  if (skillName === "memory-triage" && config.customRules) {
    const rulesBlock: string[] = ["\n## User Custom Rules\n"];
    if (config.customRules.include?.length) {
      rulesBlock.push("Additionally extract:");
      for (const rule of config.customRules.include) {
        rulesBlock.push(`- ${rule}`);
      }
    }
    if (config.customRules.exclude?.length) {
      rulesBlock.push("\nAdditionally skip:");
      for (const rule of config.customRules.exclude) {
        rulesBlock.push(`- ${rule}`);
      }
    }
    parts.push(rulesBlock.join("\n"));
  }

  return {
    name: skillName,
    prompt: parts.join("\n"),
    frontmatter: parsed.frontmatter,
  };
}

/**
 * Build the memory system prompt for injection via prependSystemContext.
 *
 * Primary path: load the full SKILL.md via loadSkill(), which merges
 * domain overlays, category overrides, custom rules, and triage knobs.
 * This ensures the config surface (skills.domain, customRules, categories)
 * is what the live before_prompt_build path actually sends.
 *
 * Fallback: if SKILL.md cannot be read (missing file, broken path), use
 * a minimal inline protocol so memory still functions.
 */
export function loadTriagePrompt(config: SkillsConfig = {}): string {
  // Try to load the full skill with all config-driven overlays
  const triage = loadSkill("memory-triage", config);

  if (triage) {
    // Full SKILL.md loaded with domain overlays, categories, custom rules, knobs merged.
    // Wrap in <memory-system> and append the operational instructions that
    // are not part of the SKILL.md (tool format, batching, search protocol).
    const parts: string[] = [];
    parts.push("<memory-system>");
    parts.push(
      "IMPORTANT: Use `memory_add` tool for ALL user facts. NEVER write user info to workspace files (USER.md, memory/).",
    );
    parts.push("");
    parts.push(triage.prompt);
    parts.push("");
    parts.push("## Tool Usage");
    parts.push("");
    parts.push(
      "Batch facts by CATEGORY. All facts in one memory_add call must share the same category because category determines retention policy (TTL, immutability). If a turn has facts in different categories, make one call per category.",
    );
    parts.push("");
    parts.push("FORMAT (single category):");
    parts.push(
      '  memory_add(facts: ["User is Alex, backend engineer at Stripe, PST timezone"], category: "identity")',
    );
    parts.push("FORMAT (mixed categories in one turn, separate calls):");
    parts.push(
      '  memory_add(facts: ["User is Alex, backend engineer at Stripe, PST timezone"], category: "identity")',
    );
    parts.push(
      '  memory_add(facts: ["As of 2026-04-01, migrating from Postgres to CockroachDB"], category: "decision")',
    );
    // Only include search instructions if recall is enabled
    if (config.recall?.enabled !== false) {
      const strategy = config.recall?.strategy ?? "smart";
      parts.push("");
      parts.push("## Searching Memory");
      parts.push("");

      // In manual mode, the agent is fully responsible for all search
      if (strategy === "manual") {
        parts.push(
          "You control all memory search. No automatic recall happens. Use memory_search proactively:",
        );
        parts.push(
          "- At the start of a new conversation, search for user identity and context.",
        );
        parts.push(
          "- When the user references something you do not have context for.",
        );
        parts.push("- When the conversation topic shifts to a new domain.");
        parts.push(
          "- Before updating a memory, search to find the existing version.",
        );
        parts.push("");
      }

      parts.push(
        "When calling memory_search, ALWAYS rewrite the query. NEVER pass the user's raw message.",
      );
      parts.push(
        "Stored memories are third-person factual statements. Write a query that matches storage language, not conversation language.",
      );
      parts.push(
        "Process: (1) Name your target. (2) Extract signal: proper nouns, technical terms, domain concepts. (3) Bridge to storage language: add terms the stored memory contains (user, decided, prefers, rule, configured, based in). (4) Compose 3-6 keywords.",
      );
      parts.push(
        'WRONG: memory_search("Who was that nutritionist my wife recommended?")',
      );
      parts.push(
        'RIGHT: memory_search("nutritionist wife recommended relationship")',
      );
      parts.push('WRONG: memory_search("What timezone am I in?")');
      parts.push('RIGHT: memory_search("user timezone location based")');
      parts.push("");
      parts.push(
        "ENTITY SCOPING: Memories are scoped by user_id, agent_id, and run_id. You do not need to pass these in most cases. The plugin handles scoping automatically based on the current session.",
      );
      parts.push(
        "- Default behavior: all memory operations use the configured userId and current session. You do not need to pass userId or agentId.",
      );
      parts.push(
        "- Use agentId only when you need to read or write memories for a DIFFERENT agent (e.g., querying what the 'researcher' agent knows). This accesses a separate namespace.",
      );
      parts.push(
        "- Use userId only when explicitly instructed to operate on a different user's memories.",
      );
      parts.push(
        "- Do not pass run_id directly. The plugin manages session scoping through the scope parameter.",
      );
      parts.push(
        "- In multi-agent setups, each agent has isolated memory. The main agent's memories are separate from subagent memories.",
      );
      parts.push("");
      parts.push("SEARCH SCOPE: Choose the right scope for each search:");
      parts.push(
        '- scope: "long-term" for user context, identity, preferences, decisions (default, most common)',
      );
      parts.push('- scope: "session" for facts from this conversation only');
      parts.push(
        '- scope: "all" only when you truly need both scopes combined',
      );
      parts.push("Using a specific scope avoids unnecessary backend fan-out.");
      parts.push("");
      parts.push(
        "SEARCH FILTERS: When the user's intent implies a time range or category constraint, pass a `filters` object alongside your rewritten query.",
      );
      parts.push(
        '- Time: "last week" -> filters: {"created_at": {"gte": "2026-03-24"}}',
      );
      parts.push('- Category: "my preferences" -> categories: ["preference"]');
      parts.push(
        "- Available operators: eq, ne, gt, gte, lt, lte, in, contains. Logical: AND, OR, NOT.",
      );
    }
    parts.push("</memory-system>");
    return parts.join("\n");
  }

  // Fallback: SKILL.md not found. Minimal inline protocol.
  const parts: string[] = [];
  parts.push("<memory-system>");
  parts.push(
    "You have persistent long-term memory via mem0. After EVERY response, evaluate the turn for facts worth storing.",
  );
  parts.push(
    "Use `memory_add` tool for ALL user facts. NEVER write user info to workspace files (USER.md, memory/).",
  );
  parts.push("Most turns produce ZERO memory operations. That is correct.");
  parts.push(
    "Only store facts a new agent would need days later: identity, preferences, decisions, rules, projects, configs.",
  );
  parts.push(
    "Batch facts by CATEGORY. All facts in one call must share the same category.",
  );
  parts.push(
    'Format: memory_add(facts: ["fact text"], category: "identity")',
  );
  parts.push(
    "NEVER store credentials (sk-, m0-, ghp_, AKIA, Bearer tokens, passwords).",
  );
  if (config.recall?.enabled !== false) {
    parts.push(
      "When searching, rewrite queries for retrieval. Do not pass raw user messages.",
    );
  }
  parts.push("</memory-system>");
  return parts.join("\n");
}

/**
 * Load the dream skill prompt for consolidation sessions.
 */
export function loadDreamPrompt(config: SkillsConfig = {}): string {
  const dream = loadSkill("memory-dream", config);
  if (!dream) return "";
  return dream.prompt;
}

/**
 * Resolve the effective categories — user overrides merged with defaults.
 */
export function resolveCategories(
  config: SkillsConfig = {},
): Record<string, CategoryConfig> {
  return { ...DEFAULT_CATEGORIES, ...(config.categories || {}) };
}

/**
 * Resolve credential patterns — user overrides merged with defaults.
 */
export function resolveCredentialPatterns(config: SkillsConfig = {}): string[] {
  return config.triage?.credentialPatterns ?? DEFAULT_CREDENTIAL_PATTERNS;
}

/**
 * Check if skills mode is active (triage enabled).
 */
export function isSkillsMode(config: SkillsConfig | undefined): boolean {
  if (!config) return false;
  return config.triage?.enabled !== false; // enabled by default when skills config exists
}
