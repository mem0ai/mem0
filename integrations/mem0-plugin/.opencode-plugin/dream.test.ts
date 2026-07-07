import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  loadDreamConfig,
  incrementSessionCount,
  checkCheapGates,
  checkMemoryGate,
  acquireDreamLock,
  releaseDreamLock,
  recordDreamCompletion,
  DREAM_DEFAULTS,
  DREAM_PROTOCOL,
} from "./dream";

let dir: string;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "mem0-dream-"));
});

afterEach(() => {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
  delete process.env.MEM0_DREAM;
});

describe("auto-dream gates", () => {
  test("memory gate passes at >= minMemories, fails below", () => {
    expect(checkMemoryGate(DREAM_DEFAULTS.minMemories, {}).pass).toBe(true);
    expect(checkMemoryGate(DREAM_DEFAULTS.minMemories - 1, {}).pass).toBe(false);
  });

  test("cheap gates: fresh state blocks on session count, passes after enough sessions", () => {
    // Fresh state: time gate passes (lastConsolidatedAt=0), but 0 sessions blocks.
    expect(checkCheapGates(dir, {}).proceed).toBe(false);
    for (let i = 0; i < DREAM_DEFAULTS.minSessions; i++) {
      incrementSessionCount(dir, `ses_${i}`);
    }
    expect(checkCheapGates(dir, {}).proceed).toBe(true);
  });

  test("incrementSessionCount only counts distinct session ids", () => {
    incrementSessionCount(dir, "ses_a");
    incrementSessionCount(dir, "ses_a");
    incrementSessionCount(dir, "ses_a");
    expect(checkCheapGates(dir, { minHours: 0 }).reason).toContain("sessions: 1");
  });

  test("recordDreamCompletion resets gates (recent time blocks again)", () => {
    for (let i = 0; i < 6; i++) incrementSessionCount(dir, `ses_${i}`);
    expect(checkCheapGates(dir, {}).proceed).toBe(true);
    recordDreamCompletion(dir);
    const r = checkCheapGates(dir, {});
    expect(r.proceed).toBe(false);
    expect(r.reason).toContain("time");
  });

  test("dream lock is exclusive and reclaimable after release", () => {
    expect(acquireDreamLock(dir)).toBe(true);
    expect(acquireDreamLock(dir)).toBe(false);
    releaseDreamLock(dir);
    expect(acquireDreamLock(dir)).toBe(true);
  });
});

describe("dream config", () => {
  test("defaults when no settings file", () => {
    const cfg = loadDreamConfig(dir);
    expect(cfg.enabled).toBe(true);
    expect(cfg.auto).toBe(true);
    expect(cfg.minMemories).toBe(DREAM_DEFAULTS.minMemories);
  });

  test("MEM0_DREAM=false force-disables", () => {
    process.env.MEM0_DREAM = "false";
    expect(loadDreamConfig(dir).enabled).toBe(false);
  });

  test("settings.json dream block overrides defaults", () => {
    writeFileSync(
      join(dir, "settings.json"),
      JSON.stringify({ dream: { minMemories: 99, auto: false } }),
    );
    const cfg = loadDreamConfig(dir);
    expect(cfg.minMemories).toBe(99);
    expect(cfg.auto).toBe(false);
    expect(cfg.enabled).toBe(true);
  });

  test("protocol uses native tools, not the MCP tool", () => {
    expect(DREAM_PROTOCOL).toContain("get_memories");
    expect(DREAM_PROTOCOL).toContain("add_memory");
    expect(DREAM_PROTOCOL).not.toContain("mem0_memory");
  });
});
