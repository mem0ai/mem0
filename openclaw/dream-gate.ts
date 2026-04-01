/**
 * Dream Gate — activity tracking, gate logic, and lock mechanism
 * for automatic memory consolidation.
 *
 * State persists in the plugin's stateDir so it survives gateway restarts.
 * Lock prevents concurrent consolidation runs.
 */

import * as fs from "fs";
import * as path from "path";

// ============================================================================
// Types
// ============================================================================

interface DreamState {
  lastConsolidatedAt: number; // ms since epoch, 0 = never
  sessionsSince: number;      // interactive sessions since last consolidation
  lastSessionId: string | null;
}

interface DreamLock {
  pid: number;
  startedAt: number;
}

interface DreamGateConfig {
  minHours: number;
  minSessions: number;
  minMemories: number;
}

const DEFAULTS: DreamGateConfig = {
  minHours: 24,
  minSessions: 5,
  minMemories: 20,
};

const LOCK_STALE_MS = 60 * 60 * 1000; // 1 hour

// ============================================================================
// State Persistence
// ============================================================================

function statePath(stateDir: string): string {
  return path.join(stateDir, "dream-state.json");
}

function lockPath(stateDir: string): string {
  return path.join(stateDir, "dream.lock");
}

function ensureDir(dir: string): void {
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch { /* exists */ }
}

function readState(stateDir: string): DreamState {
  try {
    const raw = fs.readFileSync(statePath(stateDir), "utf-8");
    return JSON.parse(raw) as DreamState;
  } catch {
    return { lastConsolidatedAt: 0, sessionsSince: 0, lastSessionId: null };
  }
}

function writeState(stateDir: string, state: DreamState): void {
  ensureDir(stateDir);
  fs.writeFileSync(statePath(stateDir), JSON.stringify(state, null, 2));
}

// ============================================================================
// Session Tracking
// ============================================================================

/**
 * Called from agent_end on every interactive turn.
 * Increments session counter (deduped by sessionId).
 */
export function incrementSessionCount(stateDir: string, sessionId: string): void {
  const state = readState(stateDir);
  if (state.lastSessionId !== sessionId) {
    state.sessionsSince++;
    state.lastSessionId = sessionId;
    writeState(stateDir, state);
  }
}

// ============================================================================
// Gate Logic
// ============================================================================

/**
 * Check all three gates. Returns true only if ALL pass.
 * Gates are checked cheapest-first (time, session, memory).
 */
export async function shouldDream(
  stateDir: string,
  config: { minHours?: number; minSessions?: number; minMemories?: number },
  memoryCount: number,
): Promise<{ pass: boolean; reason?: string }> {
  const cfg: DreamGateConfig = {
    minHours: config.minHours ?? DEFAULTS.minHours,
    minSessions: config.minSessions ?? DEFAULTS.minSessions,
    minMemories: config.minMemories ?? DEFAULTS.minMemories,
  };

  const state = readState(stateDir);

  // Gate 1: Time
  const hoursSince = (Date.now() - state.lastConsolidatedAt) / 3_600_000;
  if (hoursSince < cfg.minHours) {
    return { pass: false, reason: `time: ${hoursSince.toFixed(1)}h < ${cfg.minHours}h` };
  }

  // Gate 2: Sessions
  if (state.sessionsSince < cfg.minSessions) {
    return { pass: false, reason: `sessions: ${state.sessionsSince} < ${cfg.minSessions}` };
  }

  // Gate 3: Memory count
  if (memoryCount < cfg.minMemories) {
    return { pass: false, reason: `memories: ${memoryCount} < ${cfg.minMemories}` };
  }

  return { pass: true };
}

// ============================================================================
// Lock
// ============================================================================

/**
 * Try to acquire the dream lock. Returns true if acquired.
 * Stale locks (older than 1 hour) are reclaimed.
 */
export function acquireDreamLock(stateDir: string): boolean {
  ensureDir(stateDir);
  const lp = lockPath(stateDir);

  // Check existing lock
  try {
    const raw = fs.readFileSync(lp, "utf-8");
    const lock = JSON.parse(raw) as DreamLock;
    const age = Date.now() - lock.startedAt;
    if (age < LOCK_STALE_MS) {
      // Lock is held and not stale
      return false;
    }
    // Stale lock, reclaim
  } catch {
    // No lock file, proceed
  }

  // Write lock
  const lock: DreamLock = { pid: process.pid, startedAt: Date.now() };
  fs.writeFileSync(lp, JSON.stringify(lock));
  return true;
}

/**
 * Release the dream lock and record successful completion.
 */
export function releaseDreamLock(stateDir: string): void {
  try {
    fs.unlinkSync(lockPath(stateDir));
  } catch { /* already gone */ }
}

/**
 * Record that consolidation completed. Resets session counter.
 */
export function recordDreamCompletion(stateDir: string): void {
  const state = readState(stateDir);
  state.lastConsolidatedAt = Date.now();
  state.sessionsSince = 0;
  state.lastSessionId = null;
  writeState(stateDir, state);
}

/**
 * Get current dream state for logging/diagnostics.
 */
export function getDreamState(stateDir: string): DreamState {
  return readState(stateDir);
}
