import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import { checkCheapGates, checkMemoryGate } from "../src/dream/index.ts";

vi.mock("node:fs");

const STATE_DIR = "/tmp/test-mem0-dream";

describe("checkCheapGates", () => {
  beforeEach(() => {
    vi.mocked(fs.mkdirSync).mockReturnValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("blocks when no state file exists (zero sessions)", () => {
    vi.mocked(fs.readFileSync).mockImplementation(() => { throw new Error("ENOENT"); });
    const result = checkCheapGates(STATE_DIR, {});
    expect(result.proceed).toBe(false);
    expect(result.reason).toContain("sessions");
  });

  it("blocks when consolidated recently", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(
      JSON.stringify({ lastConsolidatedAt: Date.now() - 3_600_000, sessionsSince: 10, lastSessionId: null })
    );
    const result = checkCheapGates(STATE_DIR, {});
    expect(result.proceed).toBe(false);
    expect(result.reason).toContain("time");
  });

  it("blocks when not enough sessions", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(
      JSON.stringify({ lastConsolidatedAt: Date.now() - 48 * 3_600_000, sessionsSince: 2, lastSessionId: null })
    );
    const result = checkCheapGates(STATE_DIR, {});
    expect(result.proceed).toBe(false);
    expect(result.reason).toContain("sessions");
  });

  it("proceeds when both gates pass", () => {
    vi.mocked(fs.readFileSync).mockReturnValue(
      JSON.stringify({ lastConsolidatedAt: Date.now() - 48 * 3_600_000, sessionsSince: 10, lastSessionId: null })
    );
    expect(checkCheapGates(STATE_DIR, {}).proceed).toBe(true);
  });
});

describe("checkMemoryGate", () => {
  it("blocks when too few memories", () => {
    expect(checkMemoryGate(5, {}).pass).toBe(false);
  });

  it("passes when enough memories", () => {
    expect(checkMemoryGate(25, {}).pass).toBe(true);
  });
});
