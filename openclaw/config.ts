/**
 * Configuration parsing and default instructions/categories.
 *
 * NOTE: This module must NOT import from `node:fs` or `node:fs/promises`.
 * All filesystem operations are centralized in fs-safe.ts.
 */

import { userInfo } from "node:os";
import type { Mem0Config, Mem0Mode } from "./types.ts";

// NOTE: The gateway resolves ${VAR} syntax in openclaw.json before passing
// pluginConfig to register(). No plugin-side variable resolution needed.

// ============================================================================
// Login config fallback type — read from openclaw.json plugin section
// ============================================================================

/** Shape accepted by parse() for the openclaw.json plugin auth fallback. */
export interface FileConfig {
  apiKey?: string;
  baseUrl?: string;
}

// ============================================================================
// Default Custom Instructions & Categories
// ============================================================================

export const DEFAULT_CUSTOM_INSTRUCTIONS = `Your Task: Extract durable, actionable facts from conversations between a user and an AI assistant. Only store information that would be useful to an agent in a FUTURE session, days or weeks later.

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
- Use third person ("User prefers..." not "I prefer...")
- Keep related facts together in a single memory to preserve context
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
- Passwords, API keys, tokens, secrets, or any credentials — even when embedded in configuration blocks, setup logs, or tool output. This includes strings starting with sk-, m0-, ak_, ghp_, bot tokens (digits followed by colon and alphanumeric string), bearer tokens, webhook URLs containing tokens, pairing codes, and any long alphanumeric strings that appear in config/env contexts. Never include the actual secret value in a memory. Instead, record that the credential was configured:
  WRONG: "User's API key is sk-abc123..." or "Bot token is 12345:AABcd..."
  RIGHT: "API key was configured for the service (as of YYYY-MM-DD)" or "Telegram bot token was set up"
- One-time commands or instructions ("stop the script", "continue where you left off")
- Acknowledgments or emotional reactions ("ok", "sounds good", "you're right", "sir")
- Transient UI/navigation states ("user is in the admin panel", "relay is attached")
- Ephemeral process status ("download at 50%", "daemon not running", "still syncing")
- Cron heartbeat outputs, NO_REPLY responses, compaction flush directives
- The current date/time as a standalone fact — timestamps are conversation context, not durable knowledge. "User indicates current time is 3:25 PM" is NEVER worth storing. However, DO use timestamps to anchor other facts: "User installed Ollama on 2026-03-21" is correct.
- System routing metadata (message IDs, sender IDs, channel routing info)
- Generic small talk with no informational content
- Raw code snippets (capture the intent/decision, not the code itself)
- Information the user explicitly asks not to remember`;

export const DEFAULT_CUSTOM_CATEGORIES: Record<string, string> = {
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
  work: "Work-related context: job responsibilities, workplace dynamics, career progression, professional challenges",
  health:
    "Health-related information voluntarily shared: conditions, medications, fitness, wellness goals",
};

// ============================================================================
// Config Schema
// ============================================================================

const ALLOWED_KEYS = [
  "mode",
  "apiKey",
  "anonymousTelemetryId",
  "baseUrl",
  "userId",
  "userEmail",
  "autoCapture",
  "autoRecall",
  "customInstructions",
  "customCategories",
  "customPrompt",
  "searchThreshold",
  "topK",
  "oss",
  "skills",
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
  parse(value: unknown, fileConfig?: FileConfig): Mem0Config {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("openclaw-mem0 config required");
    }
    const cfg = value as Record<string, unknown>;
    assertAllowedKeys(cfg, ALLOWED_KEYS, "openclaw-mem0 config");

    // Only two modes: "platform" (default) or "open-source"
    if (
      typeof cfg.mode === "string" &&
      cfg.mode !== "platform" &&
      cfg.mode !== "open-source"
    ) {
      console.warn(
        `[mem0] Unknown mode "${cfg.mode}" — expected "platform" or "open-source". Defaulting to "platform".`,
      );
    }
    const mode: Mem0Mode =
      cfg.mode === "open-source" ? "open-source" : "platform";

    // Resolve API key: pluginConfig → fileConfig fallback (from openclaw.json plugin section)
    let resolvedApiKey =
      typeof cfg.apiKey === "string" ? cfg.apiKey : undefined;
    let resolvedBaseUrl =
      typeof cfg.baseUrl === "string" ? cfg.baseUrl : undefined;
    if (mode === "platform" && !resolvedApiKey && fileConfig) {
      if (fileConfig.apiKey) resolvedApiKey = fileConfig.apiKey;
      if (fileConfig.baseUrl) resolvedBaseUrl = fileConfig.baseUrl;
    }

    // Platform mode requires apiKey — but don't throw on missing config.
    // The plugin should register successfully and log a setup message.
    const needsSetup = mode === "platform" && !resolvedApiKey;

    // OpenClaw resolves ${VAR} in openclaw.json before register() — no plugin-side expansion needed
    let ossConfig: Mem0Config["oss"];
    if (cfg.oss && typeof cfg.oss === "object" && !Array.isArray(cfg.oss)) {
      ossConfig = cfg.oss as Mem0Config["oss"];
    }

    return {
      mode,
      apiKey: resolvedApiKey,
      anonymousTelemetryId:
        typeof cfg.anonymousTelemetryId === "string"
          ? cfg.anonymousTelemetryId
          : undefined,
      baseUrl: resolvedBaseUrl,
      userId:
        typeof cfg.userId === "string" && cfg.userId
          ? cfg.userId
          : (() => {
              try {
                return userInfo().username || "default";
              } catch {
                return "default";
              }
            })(),
      autoCapture: cfg.autoCapture !== false,
      autoRecall: cfg.autoRecall !== false,
      // v3.0.0: customPrompt renamed to customInstructions (backwards-compat: accept either)
      customInstructions:
        typeof cfg.customInstructions === "string"
          ? cfg.customInstructions
          : typeof cfg.customPrompt === "string"
            ? cfg.customPrompt
            : DEFAULT_CUSTOM_INSTRUCTIONS,
      customCategories:
        cfg.customCategories &&
        typeof cfg.customCategories === "object" &&
        !Array.isArray(cfg.customCategories)
          ? (cfg.customCategories as Record<string, string>)
          : DEFAULT_CUSTOM_CATEGORIES,
      searchThreshold:
        typeof cfg.searchThreshold === "number" ? cfg.searchThreshold : 0.1,
      topK: typeof cfg.topK === "number" ? cfg.topK : 5,
      needsSetup,
      oss: ossConfig,
      skills:
        cfg.skills &&
        typeof cfg.skills === "object" &&
        !Array.isArray(cfg.skills)
          ? (cfg.skills as Mem0Config["skills"])
          : undefined,
    };
  },
};
