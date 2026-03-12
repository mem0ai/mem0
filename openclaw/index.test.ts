/**
 * Regression tests for per-agent memory isolation helpers.
 *
 * Addresses review feedback: targeted coverage for auth/session state,
 * malformed input, and the resolveUserId priority chain.
 */
import { describe, it, expect } from "vitest";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
  extractAgentId,
  effectiveUserId,
  agentUserId,
  resolveUserId,
  resolveOssHistoryConfig,
} from "./index.ts";

// ---------------------------------------------------------------------------
// extractAgentId
// ---------------------------------------------------------------------------
describe("extractAgentId", () => {
  it("returns agentId from a well-formed session key", () => {
    expect(extractAgentId("agent:researcher:550e8400-e29b")).toBe("researcher");
  });

  it("returns undefined for the 'main' sentinel", () => {
    expect(extractAgentId("agent:main:abc-123")).toBeUndefined();
  });

  it("returns undefined for undefined/null/empty input", () => {
    expect(extractAgentId(undefined)).toBeUndefined();
    expect(extractAgentId("")).toBeUndefined();
  });

  it("returns undefined for non-agent session keys", () => {
    expect(extractAgentId("user:alice:xyz")).toBeUndefined();
    expect(extractAgentId("some-random-uuid")).toBeUndefined();
  });

  it("handles keys with extra colons after the UUID portion", () => {
    expect(extractAgentId("agent:beta:uuid:extra:stuff")).toBe("beta");
  });

  it("returns undefined when agentId segment is empty", () => {
    // pattern: agent::<uuid> — empty agentId
    expect(extractAgentId("agent::some-uuid")).toBeUndefined();
  });

  it("returns undefined when key is only 'agent:' with no trailing colon", () => {
    expect(extractAgentId("agent:")).toBeUndefined();
  });

  it("is case-sensitive (Agent != agent)", () => {
    expect(extractAgentId("Agent:researcher:uuid")).toBeUndefined();
  });

  it("handles whitespace-only agentId as truthy string", () => {
    // " " is a non-empty match — returned as-is (validation is caller's job)
    expect(extractAgentId("agent: :uuid")).toBe(" ");
  });
});

// ---------------------------------------------------------------------------
// effectiveUserId
// ---------------------------------------------------------------------------
describe("effectiveUserId", () => {
  const base = "alice";

  it("returns base userId when sessionKey is undefined", () => {
    expect(effectiveUserId(base)).toBe("alice");
    expect(effectiveUserId(base, undefined)).toBe("alice");
  });

  it("returns namespaced userId for agent session keys", () => {
    expect(effectiveUserId(base, "agent:researcher:uuid-1")).toBe(
      "alice:agent:researcher",
    );
  });

  it("falls back to base for 'main' agent sessions", () => {
    expect(effectiveUserId(base, "agent:main:uuid-2")).toBe("alice");
  });

  it("falls back to base for non-agent session keys", () => {
    expect(effectiveUserId(base, "plain-session-id")).toBe("alice");
  });
});

// ---------------------------------------------------------------------------
// agentUserId
// ---------------------------------------------------------------------------
describe("agentUserId", () => {
  it("produces the correct namespaced format", () => {
    expect(agentUserId("alice", "researcher")).toBe("alice:agent:researcher");
  });

  it("handles empty agentId (caller is responsible for validation)", () => {
    expect(agentUserId("alice", "")).toBe("alice:agent:");
  });
});

// ---------------------------------------------------------------------------
// resolveUserId  —  priority chain
// ---------------------------------------------------------------------------
describe("resolveUserId", () => {
  const base = "alice";

  it("prefers explicit agentId over everything else", () => {
    expect(
      resolveUserId(
        base,
        { agentId: "researcher", userId: "bob" },
        "agent:beta:uuid",
      ),
    ).toBe("alice:agent:researcher");
  });

  it("uses explicit userId when agentId is absent", () => {
    expect(
      resolveUserId(base, { userId: "bob" }, "agent:beta:uuid"),
    ).toBe("bob");
  });

  it("derives from session key when both agentId and userId are absent", () => {
    expect(
      resolveUserId(base, {}, "agent:gamma:uuid"),
    ).toBe("alice:agent:gamma");
  });

  it("falls back to base userId when nothing else is provided", () => {
    expect(resolveUserId(base, {})).toBe("alice");
    expect(resolveUserId(base, {}, undefined)).toBe("alice");
  });

  it("ignores empty-string agentId (falsy)", () => {
    expect(resolveUserId(base, { agentId: "" })).toBe("alice");
  });

  it("ignores empty-string userId (falsy)", () => {
    expect(resolveUserId(base, { userId: "" })).toBe("alice");
  });
});

// ---------------------------------------------------------------------------
// Cross-agent isolation sanity checks
// ---------------------------------------------------------------------------
describe("multi-agent isolation", () => {
  const base = "user-42";

  it("different agents get different namespaces", () => {
    const alphaId = effectiveUserId(base, "agent:alpha:uuid-a");
    const betaId = effectiveUserId(base, "agent:beta:uuid-b");
    expect(alphaId).not.toBe(betaId);
    expect(alphaId).toBe("user-42:agent:alpha");
    expect(betaId).toBe("user-42:agent:beta");
  });

  it("same agent across sessions yields the same namespace", () => {
    const s1 = effectiveUserId(base, "agent:alpha:session-1");
    const s2 = effectiveUserId(base, "agent:alpha:session-2");
    expect(s1).toBe(s2);
  });

  it("main session shares the base namespace (no isolation)", () => {
    const mainId = effectiveUserId(base, "agent:main:uuid-m");
    expect(mainId).toBe(base);
  });
});

// ---------------------------------------------------------------------------
// OSS history sqlite config helper
// ---------------------------------------------------------------------------

describe("resolveOssHistoryConfig", () => {
  it("creates the parent directory and returns both history fields", async () => {
    const tmp = await mkdtemp(join(tmpdir(), "openclaw-mem0-"));
    try {
      const dbPath = join(tmp, "nested", "history.db");
      const result = await resolveOssHistoryConfig(dbPath);
      expect(result.historyDbPath).toBe(dbPath);
      expect(result.historyStore).toEqual({
        provider: "sqlite",
        config: { historyDbPath: dbPath },
      });
      const parent = await stat(join(tmp, "nested"));
      expect(parent.isDirectory()).toBe(true);
    } finally {
      await rm(tmp, { recursive: true, force: true });
    }
  });

  it("applies resolvePath before creating directories and wiring historyStore", async () => {
    const tmp = await mkdtemp(join(tmpdir(), "openclaw-mem0-"));
    try {
      const result = await resolveOssHistoryConfig("history.db", (p) =>
        join(tmp, "resolved", p),
      );
      expect(result.historyDbPath).toBe(join(tmp, "resolved", "history.db"));
      expect(result.historyStore).toEqual({
        provider: "sqlite",
        config: { historyDbPath: join(tmp, "resolved", "history.db") },
      });
      const parent = await stat(join(tmp, "resolved"));
      expect(parent.isDirectory()).toBe(true);
    } finally {
      await rm(tmp, { recursive: true, force: true });
    }
  });
});
