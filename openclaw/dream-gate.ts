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
 * Check cheap gates (time + sessions). These are local file reads only.
 * Call this BEFORE any API calls. If this fails, skip the expensive
 * memory count check entirely.
 */
export function checkCheapGates(
  stateDir: string,
  config: { minHours?: number; minSessions?: number },
): { proceed: boolean; reason?: string } {
  const minHours = config.minHours ?? DEFAULTS.minHours;
  const minSessions = config.minSessions ?? DEFAULTS.minSessions;
  const state = readState(stateDir);

  // Gate 1: Time (one local file read)
  const hoursSince = (Date.now() - state.lastConsolidatedAt) / 3_600_000;
  if (hoursSince < minHours) {
    return { proceed: false, reason: `time: ${hoursSince.toFixed(1)}h < ${minHours}h` };
  }

  // Gate 2: Sessions (same file, already read)
  if (state.sessionsSince < minSessions) {
    return { proceed: false, reason: `sessions: ${state.sessionsSince} < ${minSessions}` };
  }

  return { proceed: true };
}

/**
 * Check expensive memory count gate. Only call AFTER checkCheapGates passes.
 */
export function checkMemoryGate(
  memoryCount: number,
  config: { minMemories?: number },
): { pass: boolean; reason?: string } {
  const minMemories = config.minMemories ?? DEFAULTS.minMemories;
  if (memoryCount < minMemories) {
    return { pass: false, reason: `memories: ${memoryCount} < ${minMemories}` };
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
