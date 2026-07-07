/**
 * Auto-dream: gated automatic memory consolidation for the Mem0 OpenCode plugin.
 *
 * Ported from the (stable) pi-agent plugin's dream module and adapted to
 * OpenCode's hook model. When the cheap gates (time since last consolidation +
 * sessions since) and the memory-count gate all pass, the plugin injects the
 * DREAM_PROTOCOL into the agent's context so it consolidates memories (merge
 * duplicates, drop stale/sensitive entries, rewrite vague ones) before
 * answering. A filesystem lock prevents concurrent sessions from dreaming at
 * once, and completion is recorded so it won't re-trigger until the next cycle.
 *
 * State + lock live in ~/.mem0/ alongside settings.json. Opt out with
 * MEM0_DREAM=false, or tune via the `dream` block in ~/.mem0/settings.json.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";

export interface DreamConfig {
  enabled: boolean;
  auto: boolean;
  minHours: number;
  minSessions: number;
  minMemories: number;
}

interface DreamState {
  lastConsolidatedAt: number;
  sessionsSince: number;
  lastSessionId: string | null;
}

interface DreamLock {
  pid: number;
  startedAt: number;
}

const LOCK_STALE_MS = 60 * 60 * 1000;

export const DREAM_DEFAULTS: DreamConfig = {
  enabled: true,
  auto: true,
  minHours: 24,
  minSessions: 5,
  minMemories: 20,
};

function statePath(stateDir: string): string {
  return join(stateDir, "mem0-dream-state.json");
}

function lockPath(stateDir: string): string {
  return join(stateDir, "mem0-dream.lock");
}

function ensureDir(dir: string): void {
  try {
    mkdirSync(dir, { recursive: true });
  } catch {
    /* exists */
  }
}

function readState(stateDir: string): DreamState {
  try {
    return JSON.parse(readFileSync(statePath(stateDir), "utf-8")) as DreamState;
  } catch {
    return { lastConsolidatedAt: 0, sessionsSince: 0, lastSessionId: null };
  }
}

function writeState(stateDir: string, state: DreamState): void {
  ensureDir(stateDir);
  writeFileSync(statePath(stateDir), JSON.stringify(state, null, 2));
}

/**
 * Load dream config from ~/.mem0/settings.json (`dream` block), applying
 * defaults. MEM0_DREAM=false (or 0/no/off) force-disables regardless.
 */
export function loadDreamConfig(settingsDir: string): DreamConfig {
  let envEnabled: boolean | undefined;
  const env = process.env.MEM0_DREAM;
  if (env !== undefined) {
    const s = env.toLowerCase();
    envEnabled = s !== "false" && s !== "0" && s !== "no" && s !== "off";
  }

  let cfg: DreamConfig = { ...DREAM_DEFAULTS };
  try {
    const sp = join(settingsDir, "settings.json");
    if (existsSync(sp)) {
      const settings = JSON.parse(readFileSync(sp, "utf-8"));
      const d = settings?.dream;
      if (d && typeof d === "object") {
        cfg = {
          enabled: typeof d.enabled === "boolean" ? d.enabled : cfg.enabled,
          auto: typeof d.auto === "boolean" ? d.auto : cfg.auto,
          minHours: typeof d.minHours === "number" ? d.minHours : cfg.minHours,
          minSessions: typeof d.minSessions === "number" ? d.minSessions : cfg.minSessions,
          minMemories: typeof d.minMemories === "number" ? d.minMemories : cfg.minMemories,
        };
      }
    }
  } catch {
    /* defaults */
  }

  if (envEnabled !== undefined) cfg.enabled = envEnabled;
  return cfg;
}

/** Count a new session toward the dream gate (once per distinct sessionId). */
export function incrementSessionCount(stateDir: string, sessionId: string): void {
  const state = readState(stateDir);
  if (state.lastSessionId !== sessionId) {
    state.sessionsSince++;
    state.lastSessionId = sessionId;
    writeState(stateDir, state);
  }
}

/** Cheap gates that don't need an API call: time since last + sessions since. */
export function checkCheapGates(
  stateDir: string,
  config: Partial<DreamConfig>,
): { proceed: boolean; reason?: string } {
  const minHours = config.minHours ?? DREAM_DEFAULTS.minHours;
  const minSessions = config.minSessions ?? DREAM_DEFAULTS.minSessions;
  const state = readState(stateDir);

  const hoursSince = (Date.now() - state.lastConsolidatedAt) / 3_600_000;
  if (hoursSince < minHours) {
    return { proceed: false, reason: `time: ${hoursSince.toFixed(1)}h < ${minHours}h` };
  }
  if (state.sessionsSince < minSessions) {
    return { proceed: false, reason: `sessions: ${state.sessionsSince} < ${minSessions}` };
  }
  return { proceed: true };
}

/** Memory-count gate (uses the count already fetched at session init). */
export function checkMemoryGate(
  memoryCount: number,
  config: Partial<DreamConfig>,
): { pass: boolean; reason?: string } {
  const minMemories = config.minMemories ?? DREAM_DEFAULTS.minMemories;
  if (memoryCount < minMemories) {
    return { pass: false, reason: `memories: ${memoryCount} < ${minMemories}` };
  }
  return { pass: true };
}

/** Acquire an exclusive dream lock (stale locks > 1h are reclaimed). */
export function acquireDreamLock(stateDir: string): boolean {
  ensureDir(stateDir);
  const lp = lockPath(stateDir);

  try {
    const lock = JSON.parse(readFileSync(lp, "utf-8")) as DreamLock;
    if (Date.now() - lock.startedAt < LOCK_STALE_MS) {
      return false;
    }
    try {
      unlinkSync(lp);
    } catch {
      /* race ok */
    }
  } catch {
    /* no lock file */
  }

  const lock: DreamLock = { pid: process.pid, startedAt: Date.now() };
  try {
    writeFileSync(lp, JSON.stringify(lock), { flag: "wx" });
    return true;
  } catch {
    return false;
  }
}

export function releaseDreamLock(stateDir: string): void {
  try {
    unlinkSync(lockPath(stateDir));
  } catch {
    /* already gone */
  }
}

/** Reset the gates after a successful consolidation. */
export function recordDreamCompletion(stateDir: string): void {
  const state = readState(stateDir);
  state.lastConsolidatedAt = Date.now();
  state.sessionsSince = 0;
  state.lastSessionId = null;
  writeState(stateDir, state);
}

/**
 * Consolidation protocol injected into the agent context when a dream is
 * triggered. Uses the plugin's native OpenCode memory tools (get_memories /
 * add_memory / delete_memory) rather than an MCP tool.
 */
export const DREAM_PROTOCOL = `<mem0-dream>
You are running memory consolidation. Complete these steps using the mem0 memory tools (get_memories, add_memory, delete_memory):

1. ORIENT — Call get_memories to list all memories. Count by category. Note oldest/newest.

2. GATHER TARGETS — Review each memory. Classify as:
   - DELETE: sensitive information (API keys, passwords, tokens), expired/stale entries, noise, redundant operational details
   - MERGE: near-duplicates (same fact stated differently). Keep the better-worded one, delete the other.
   - REWRITE: vague, first-person, or poorly-categorized entries. add_memory with improved text, then delete_memory the old one.
   - KEEP: everything else.
   Skip any memory starting with "[PINNED]".

3. CONSOLIDATE — Execute the changes:
   - Delete stale/duplicate entries with delete_memory
   - For merges: add_memory the merged text, delete_memory both originals
   - For rewrites: add_memory the improved version, delete_memory the original

4. REPORT — Summarize: how many reviewed, deleted, merged, rewritten, final count.

Quality targets: zero sensitive data stored, zero duplicates, all entries are atomic (one fact each), 15-50 words each.
After consolidation, respond to the user's message normally.
</mem0-dream>`;
