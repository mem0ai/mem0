/**
 * Tests for dream-gate.ts — activity tracking, gate logic, and lock mechanism
 * for automatic memory consolidation.
 *
 * All filesystem operations are mocked via fs-safe.ts.
 * Time-dependent tests use vi.useFakeTimers().
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../fs-safe.ts", () => ({
  readText: vi.fn(),
  writeText: vi.fn(),
  mkdirp: vi.fn(),
  unlink: vi.fn(),
}));

import { readText, writeText, mkdirp, unlink } from "../fs-safe.ts";
import {
  incrementSessionCount,
  checkCheapGates,
  checkMemoryGate,
  acquireDreamLock,
  releaseDreamLock,
  recordDreamCompletion,
  getDreamState,
} from "../dream-gate.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockReadText = readText as ReturnType<typeof vi.fn>;
const mockWriteText = writeText as ReturnType<typeof vi.fn>;
const mockMkdirp = mkdirp as ReturnType<typeof vi.fn>;
const mockUnlink = unlink as ReturnType<typeof vi.fn>;

const STATE_DIR = "/tmp/test-state";

interface DreamState {
  lastConsolidatedAt: number;
  sessionsSince: number;
  lastSessionId: string | null;
}

function setDreamState(state: DreamState): void {
  mockReadText.mockImplementation((filePath: string) => {
    if (filePath.endsWith("dream-state.json")) {
      return JSON.stringify(state);
    }
    throw new Error("ENOENT");
  });
}

function setNoState(): void {
  mockReadText.mockImplementation(() => {
    throw new Error("ENOENT");
  });
}

function getWrittenState(): DreamState {
  const call = mockWriteText.mock.calls.find((c: unknown[]) =>
    (c[0] as string).endsWith("dream-state.json"),
  );
  if (!call) throw new Error("No state file written");
  return JSON.parse(call[1] as string);
}

beforeEach(() => {
  vi.resetAllMocks();
  mockMkdirp.mockReturnValue(undefined);
  mockUnlink.mockReturnValue(undefined);
});

// ---------------------------------------------------------------------------
// incrementSessionCount
// ---------------------------------------------------------------------------

describe("incrementSessionCount", () => {
  it("increments counter for a new session", () => {
    setDreamState({
      lastConsolidatedAt: 0,
      sessionsSince: 3,
      lastSessionId: "session-old",
    });

    incrementSessionCount(STATE_DIR, "session-new");

    const written = getWrittenState();
    expect(written.sessionsSince).toBe(4);
    expect(written.lastSessionId).toBe("session-new");
  });

  it("deduplicates same session (no increment)", () => {
    setDreamState({
      lastConsolidatedAt: 0,
      sessionsSince: 3,
      lastSessionId: "session-same",
    });

    incrementSessionCount(STATE_DIR, "session-same");

    // writeText should NOT have been called for the state file
    const stateWrites = mockWriteText.mock.calls.filter((c: unknown[]) =>
      (c[0] as string).endsWith("dream-state.json"),
    );
    expect(stateWrites).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// checkCheapGates
// ---------------------------------------------------------------------------

describe("checkCheapGates", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fails time gate when consolidation was too recent", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // Last consolidated 1 hour ago, but minHours is 24
    setDreamState({
      lastConsolidatedAt: now - 1 * 3_600_000,
      sessionsSince: 100,
      lastSessionId: null,
    });

    const result = checkCheapGates(STATE_DIR, { minHours: 24, minSessions: 5 });
    expect(result.proceed).toBe(false);
    expect(result.reason).toContain("time");
  });

  it("fails session gate when too few sessions", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // Last consolidated 48 hours ago (passes time gate), but only 2 sessions
    setDreamState({
      lastConsolidatedAt: now - 48 * 3_600_000,
      sessionsSince: 2,
      lastSessionId: null,
    });

    const result = checkCheapGates(STATE_DIR, {
      minHours: 24,
      minSessions: 5,
    });
    expect(result.proceed).toBe(false);
    expect(result.reason).toContain("sessions");
  });

  it("passes both gates when conditions are met", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // 48 hours ago, 10 sessions — both gates pass
    setDreamState({
      lastConsolidatedAt: now - 48 * 3_600_000,
      sessionsSince: 10,
      lastSessionId: null,
    });

    const result = checkCheapGates(STATE_DIR, {
      minHours: 24,
      minSessions: 5,
    });
    expect(result.proceed).toBe(true);
    expect(result.reason).toBeUndefined();
  });

  it("uses defaults when config is empty", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // Never consolidated (0), 100 sessions — should pass with defaults (24h, 5 sessions)
    setDreamState({
      lastConsolidatedAt: 0,
      sessionsSince: 100,
      lastSessionId: null,
    });

    const result = checkCheapGates(STATE_DIR, {});
    expect(result.proceed).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// checkMemoryGate
// ---------------------------------------------------------------------------

describe("checkMemoryGate", () => {
  it("fails when too few memories", () => {
    const result = checkMemoryGate(5, { minMemories: 20 });
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("memories");
    expect(result.reason).toContain("5");
  });

  it("passes when enough memories", () => {
    const result = checkMemoryGate(25, { minMemories: 20 });
    expect(result.pass).toBe(true);
    expect(result.reason).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// acquireDreamLock
// ---------------------------------------------------------------------------

describe("acquireDreamLock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("succeeds when no lock exists", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // readText throws for lock file (not found), writeText succeeds for wx create
    mockReadText.mockImplementation(() => {
      throw new Error("ENOENT");
    });
    mockWriteText.mockReturnValue(undefined);

    const result = acquireDreamLock(STATE_DIR);
    expect(result).toBe(true);

    // Verify it wrote a lock file with wx flag
    const lockWrite = mockWriteText.mock.calls.find((c: unknown[]) =>
      (c[0] as string).endsWith("dream.lock"),
    );
    expect(lockWrite).toBeDefined();
    const lockData = JSON.parse(lockWrite![1] as string);
    expect(lockData.pid).toBe(process.pid);
    expect(lockData.startedAt).toBe(now);
    expect(lockWrite![2]).toEqual({ flag: "wx" });
  });

  it("fails when lock exists and is fresh", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // Lock was created 10 minutes ago — still fresh (< 1 hour)
    mockReadText.mockImplementation((filePath: string) => {
      if (filePath.endsWith("dream.lock")) {
        return JSON.stringify({
          pid: 12345,
          startedAt: now - 10 * 60 * 1000,
        });
      }
      throw new Error("ENOENT");
    });

    const result = acquireDreamLock(STATE_DIR);
    expect(result).toBe(false);

    // Should NOT have written a new lock
    const lockWrites = mockWriteText.mock.calls.filter((c: unknown[]) =>
      (c[0] as string).endsWith("dream.lock"),
    );
    expect(lockWrites).toHaveLength(0);
  });

  it("succeeds when lock is stale (>1hr old)", () => {
    const now = Date.now();
    vi.setSystemTime(now);

    // Lock was created 2 hours ago — stale
    mockReadText.mockImplementation((filePath: string) => {
      if (filePath.endsWith("dream.lock")) {
        return JSON.stringify({
          pid: 99999,
          startedAt: now - 2 * 60 * 60 * 1000,
        });
      }
      throw new Error("ENOENT");
    });
    mockWriteText.mockReturnValue(undefined);

    const result = acquireDreamLock(STATE_DIR);
    expect(result).toBe(true);

    // Should have unlinked the stale lock
    expect(mockUnlink).toHaveBeenCalled();

    // Should have written a new lock
    const lockWrite = mockWriteText.mock.calls.find((c: unknown[]) =>
      (c[0] as string).endsWith("dream.lock"),
    );
    expect(lockWrite).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// releaseDreamLock
// ---------------------------------------------------------------------------

describe("releaseDreamLock", () => {
  it("removes lock file", () => {
    releaseDreamLock(STATE_DIR);
    expect(mockUnlink).toHaveBeenCalledWith(
      expect.stringContaining("dream.lock"),
    );
  });
});

// ---------------------------------------------------------------------------
// recordDreamCompletion
// ---------------------------------------------------------------------------

describe("recordDreamCompletion", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resets session counter and records timestamp", () => {
    const now = 1700000000000;
    vi.setSystemTime(now);

    setDreamState({
      lastConsolidatedAt: 0,
      sessionsSince: 15,
      lastSessionId: "session-xyz",
    });

    recordDreamCompletion(STATE_DIR);

    const written = getWrittenState();
    expect(written.lastConsolidatedAt).toBe(now);
    expect(written.sessionsSince).toBe(0);
    expect(written.lastSessionId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getDreamState
// ---------------------------------------------------------------------------

describe("getDreamState", () => {
  it("returns default state when no file exists", () => {
    setNoState();

    const state = getDreamState(STATE_DIR);
    expect(state).toEqual({
      lastConsolidatedAt: 0,
      sessionsSince: 0,
      lastSessionId: null,
    });
  });

  it("returns persisted state when file exists", () => {
    const persisted = {
      lastConsolidatedAt: 1700000000000,
      sessionsSince: 7,
      lastSessionId: "session-abc",
    };
    setDreamState(persisted);

    const state = getDreamState(STATE_DIR);
    expect(state).toEqual(persisted);
  });
});
