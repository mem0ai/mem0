import * as fs from "node:fs";
import * as path from "node:path";
import type { DreamState, DreamLock, DreamConfig } from "../types.ts";

const LOCK_STALE_MS = 60 * 60 * 1000;

const DEFAULTS: DreamConfig = {
  enabled: true,
  auto: true,
  minHours: 24,
  minSessions: 5,
  minMemories: 20,
};

function statePath(stateDir: string): string {
  return path.join(stateDir, "mem0-dream-state.json");
}

function lockPath(stateDir: string): string {
  return path.join(stateDir, "mem0-dream.lock");
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

export function getDreamState(stateDir: string): DreamState {
  return readState(stateDir);
}

export function incrementSessionCount(stateDir: string, sessionId: string): void {
  const state = readState(stateDir);
  if (state.lastSessionId !== sessionId) {
    state.sessionsSince++;
    state.lastSessionId = sessionId;
    writeState(stateDir, state);
  }
}

export function checkCheapGates(
  stateDir: string,
  config: Partial<DreamConfig>,
): { proceed: boolean; reason?: string } {
  const minHours = config.minHours ?? DEFAULTS.minHours;
  const minSessions = config.minSessions ?? DEFAULTS.minSessions;
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

export function checkMemoryGate(
  memoryCount: number,
  config: Partial<DreamConfig>,
): { pass: boolean; reason?: string } {
  const minMemories = config.minMemories ?? DEFAULTS.minMemories;
  if (memoryCount < minMemories) {
    return { pass: false, reason: `memories: ${memoryCount} < ${minMemories}` };
  }
  return { pass: true };
}

export function acquireDreamLock(stateDir: string): boolean {
  ensureDir(stateDir);
  const lp = lockPath(stateDir);

  try {
    const raw = fs.readFileSync(lp, "utf-8");
    const lock = JSON.parse(raw) as DreamLock;
    if (Date.now() - lock.startedAt < LOCK_STALE_MS) {
      return false;
    }
    try { fs.unlinkSync(lp); } catch { /* race ok */ }
  } catch { /* no lock file */ }

  const lock: DreamLock = { pid: process.pid, startedAt: Date.now() };
  try {
    fs.writeFileSync(lp, JSON.stringify(lock), { flag: "wx" });
    return true;
  } catch {
    return false;
  }
}

export function releaseDreamLock(stateDir: string): void {
  try { fs.unlinkSync(lockPath(stateDir)); } catch { /* already gone */ }
}

export function recordDreamCompletion(stateDir: string): void {
  const state = readState(stateDir);
  state.lastConsolidatedAt = Date.now();
  state.sessionsSince = 0;
  state.lastSessionId = null;
  writeState(stateDir, state);
}
