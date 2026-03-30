/**
 * Skill Loader — reads skill markdown files, merges domain overlays,
 * injects user config, and produces the final injectable prompt string.
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import type { SkillsConfig, CategoryConfig } from "./types.ts";

// ============================================================================
// Defaults
// ============================================================================

const DEFAULT_CATEGORIES: Record<string, CategoryConfig> = {
  configuration: { importance: 0.95, ttl: null },
  rule: { importance: 0.90, ttl: null },
  identity: { importance: 0.95, ttl: null, immutable: true },
  preference: { importance: 0.85, ttl: null },
  decision: { importance: 0.80, ttl: null },
  technical: { importance: 0.80, ttl: null },
  relationship: { importance: 0.75, ttl: null },
  project: { importance: 0.75, ttl: "90d" },
  operational: { importance: 0.60, ttl: "7d" },
};

const DEFAULT_CREDENTIAL_PATTERNS = [
  "sk-", "m0-", "ghp_", "AKIA", "ak_", "Bearer ",
  "bot\\d+:AA", "password=", "token=", "secret=",
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
  } catch { /* import.meta.url may not be available */ }

  // Strategy 2: __dirname (works in CJS / jiti)
  if (typeof __dirname !== "undefined") {
    candidates.push(path.join(__dirname, "skills"));
    candidates.push(path.join(__dirname, "..", "skills"));
  }

  // Validate: must contain the expected subdirectory structure
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, "memory-triage", "SKILL.md"))) {
      return dir;
    }
  }

  return candidates[0] ?? "skills"; // Will fail gracefully in readSkillFile
}

const SKILLS_DIR = resolveSkillsDir();

function readSkillFile(skillName: string): string | null {
  // Skills use OpenClaw directory format: <skill-name>/SKILL.md
  const filePath = path.join(SKILLS_DIR, skillName, "SKILL.md");
  try {
    return fs.readFileSync(filePath, "utf-8");
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
  // Domain overlays are stored inside the target skill's directory
  const filePath = path.join(SKILLS_DIR, targetSkill, "domains", `${domain}.md`);
  try {
    const content = fs.readFileSync(filePath, "utf-8");
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

function renderCategoriesBlock(categories: Record<string, CategoryConfig>): string {
  const lines: string[] = ["\n## Active Category Configuration (overrides defaults above)\n"];
  for (const [name, cat] of Object.entries(categories)) {
    const ttlLabel = cat.ttl ? `expires: ${cat.ttl}` : "permanent";
    const immLabel = cat.immutable ? ", immutable" : "";
    lines.push(`- **${name.toUpperCase()}** (importance: ${cat.importance} | ${ttlLabel}${immLabel})`);
  }
  return lines.join("\n");
}

function renderTriageKnobs(config: SkillsConfig): string {
  const triage = config.triage;
  if (!triage) return "";

  const lines: string[] = [];

  if (triage.maxFactsPerTurn !== undefined) {
    lines.push(`- Maximum ${triage.maxFactsPerTurn} store operations per turn (overrides default of 3)`);
  }
  if (triage.importanceThreshold !== undefined) {
    lines.push(`- Only store facts with importance >= ${triage.importanceThreshold}`);
  }

  const patterns = resolveCredentialPatterns(config);
  if (config.triage?.credentialPatterns) {
    lines.push(`- Credential patterns to scan: ${patterns.join(", ")}`);
  }

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

  // Inject triage knobs (maxFactsPerTurn, importanceThreshold, credentialPatterns)
  if (skillName === "memory-triage") {
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
 * Load and assemble the full triage + recall skill prompt for injection
 * into before_agent_start. Respects skills.recall.enabled.
 */
export function loadTriagePrompt(config: SkillsConfig = {}): string {
  const parts: string[] = [];

  // Inline protocol — must be present every turn since lazy skill loading
  // means the model may skip reading the SKILL.md file.
  // This is the minimal viable protocol; full details in SKILL.md.
  parts.push("<memory-system>");
  parts.push("You have persistent long-term memory via mem0. After EVERY response, evaluate the turn for facts worth storing.");
  parts.push("");
  parts.push("RULES:");
  parts.push("- Use `memory_store` tool for ALL user facts. NEVER write user info to workspace files (USER.md, memory/).");
  parts.push("- Most turns produce ZERO memory operations. That is correct.");
  parts.push("- Only store facts a new agent would need days later: identity, preferences, decisions, rules, projects, configs.");
  parts.push("- Skip: tool outputs, status checks, small talk, acknowledgments, credentials, facts already recalled.");
  parts.push("- 15-50 words per memory. Third person. Temporal anchor time-sensitive facts with 'As of YYYY-MM-DD'.");
  parts.push("- Group related facts about same entity into ONE memory_store call.");
  parts.push("- Preserve the user's exact words for opinions and preferences.");
  parts.push("");
  parts.push("FORMAT:");
  parts.push('  memory_store(text: "the fact", category: "identity|preference|decision|rule|project|configuration|technical|relationship", importance: 0.6-0.95)');
  parts.push("");
  parts.push("CREDENTIALS: NEVER store sk-, m0-, ghp_, AKIA, Bearer tokens, passwords. Store that it was configured, not the value.");
  parts.push("For the full protocol with examples, read the memory-triage skill.");
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
