/**
 * Regression tests for per-agent memory isolation helpers and
 * message filtering / deduplication logic.
 */
import { describe, it, expect } from "vitest";
import {
  extractAgentId,
  effectiveUserId,
  agentUserId,
  resolveUserId,
  isNoiseMessage,
  stripNoiseFromContent,
  filterMessagesForExtraction,
  deduplicateByContent,
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
// isNoiseMessage
// ---------------------------------------------------------------------------
describe("isNoiseMessage", () => {
  it("detects HEARTBEAT_OK", () => {
    expect(isNoiseMessage("HEARTBEAT_OK")).toBe(true);
    expect(isNoiseMessage("heartbeat_ok")).toBe(true);
  });

  it("detects NO_REPLY", () => {
    expect(isNoiseMessage("NO_REPLY")).toBe(true);
  });

  it("detects current-time stamps", () => {
    expect(
      isNoiseMessage("Current time: Friday, February 20th, 2026 — 3:58 AM (America/New_York)"),
    ).toBe(true);
  });

  it("detects single-word acknowledgments", () => {
    for (const word of ["ok", "yes", "sir", "done", "cool", "Got it", "it's on"]) {
      expect(isNoiseMessage(word)).toBe(true);
    }
  });

  it("detects system routing messages", () => {
    expect(
      isNoiseMessage("System: [2026-02-19 19:51:31 PST] Slack message edited in #D0AFV2LDGDS."),
    ).toBe(true);
    expect(
      isNoiseMessage("System: [2026-02-19 22:15:42 PST] Exec failed (gentle-b, signal 15)"),
    ).toBe(true);
  });

  it("detects compaction audit messages", () => {
    expect(
      isNoiseMessage(
        "System: [2026-02-20 16:12:04 EST] ⚠️ Post-Compaction Audit: The following required startup files were not read",
      ),
    ).toBe(true);
  });

  it("preserves real content", () => {
    expect(isNoiseMessage("Beau runs Rize Digital LLC")).toBe(false);
    expect(isNoiseMessage("Can you check the lovable discord?")).toBe(false);
    expect(isNoiseMessage("I approve the Tailscale installation")).toBe(false);
  });

  it("treats empty/whitespace as noise", () => {
    expect(isNoiseMessage("")).toBe(true);
    expect(isNoiseMessage("   ")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// stripNoiseFromContent
// ---------------------------------------------------------------------------
describe("stripNoiseFromContent", () => {
  it("removes conversation metadata JSON blocks", () => {
    const input = `Conversation info (untrusted metadata):
\`\`\`json
{
  "message_id": "499",
  "sender": "6039555582"
}
\`\`\`

What models are you currently using?`;
    const result = stripNoiseFromContent(input);
    expect(result).toBe("What models are you currently using?");
  });

  it("removes media attachment lines", () => {
    const input = "[media attached: /path/to/file.jpg (image/jpeg) | /path/to/file.jpg]\nActual question here";
    const result = stripNoiseFromContent(input);
    expect(result).toContain("Actual question here");
    expect(result).not.toContain("[media attached:");
  });

  it("removes image sending boilerplate", () => {
    const input =
      "To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg. Keep caption in the text body.\nReal content here";
    const result = stripNoiseFromContent(input);
    expect(result).toContain("Real content here");
    expect(result).not.toContain("prefer the message tool");
  });

  it("preserves content when no noise is present", () => {
    const input = "User wants to deploy to production via Vercel.";
    expect(stripNoiseFromContent(input)).toBe(input);
  });

  it("collapses excessive blank lines after stripping", () => {
    const input = "Line one\n\n\n\n\nLine two";
    expect(stripNoiseFromContent(input)).toBe("Line one\n\nLine two");
  });
});

// ---------------------------------------------------------------------------
// filterMessagesForExtraction
// ---------------------------------------------------------------------------
describe("filterMessagesForExtraction", () => {
  it("drops noise messages entirely", () => {
    const messages = [
      { role: "user", content: "HEARTBEAT_OK" },
      { role: "assistant", content: "Real response with durable facts." },
      { role: "user", content: "ok" },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("Real response with durable facts.");
  });

  it("strips noise fragments but keeps the rest", () => {
    const messages = [
      {
        role: "user",
        content: `Conversation info (untrusted metadata):
\`\`\`json
{
  "message_id": "123",
  "sender": "456"
}
\`\`\`

What is the deployment plan?`,
      },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe("What is the deployment plan?");
  });

  it("truncates long messages", () => {
    const longContent = "A".repeat(3000);
    const messages = [{ role: "assistant", content: longContent }];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].content.length).toBeLessThan(2100);
    expect(result[0].content).toContain("[...truncated]");
  });

  it("returns empty array when all messages are noise", () => {
    const messages = [
      { role: "user", content: "NO_REPLY" },
      { role: "user", content: "ok" },
      { role: "user", content: "Current time: Friday, February 20th, 2026" },
    ];
    expect(filterMessagesForExtraction(messages)).toHaveLength(0);
  });

  it("handles a realistic mixed payload", () => {
    const messages = [
      { role: "user", content: "Pre-compaction memory flush. Store durable memories now." },
      {
        role: "assistant",
        content: "## What I Accomplished\n\nDeployed the API to production with Vercel.",
      },
      { role: "user", content: "sir" },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].content).toContain("Deployed the API");
  });
});

// ---------------------------------------------------------------------------
// deduplicateByContent
// ---------------------------------------------------------------------------
describe("deduplicateByContent", () => {
  it("removes near-duplicate memories (>80% word overlap), keeping higher-scored", () => {
    const memories = [
      { id: "1", memory: "User runs Rize Digital LLC focused on tree service contractors in Texas", score: 0.9 },
      { id: "2", memory: "User runs Rize Digital LLC focused on tree service contractors in Texas and Connecticut", score: 0.85 },
    ];
    const result = deduplicateByContent(memories);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("1"); // keeps the higher-scored
  });

  it("keeps the higher-scored item even when it appears later in the array", () => {
    const memories = [
      { id: "1", memory: "User runs Rize Digital LLC focused on tree service contractors in Texas", score: 0.75 },
      { id: "2", memory: "User runs Rize Digital LLC focused on tree service contractors in Texas and Connecticut", score: 0.92 },
    ];
    const result = deduplicateByContent(memories);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("2"); // higher score wins regardless of position
  });

  it("keeps distinct memories", () => {
    const memories = [
      { id: "1", memory: "User prefers dark mode", score: 0.9 },
      { id: "2", memory: "User's Tailscale IP is 100.71.135.41", score: 0.85 },
    ];
    const result = deduplicateByContent(memories);
    expect(result).toHaveLength(2);
  });

  it("handles empty and single-element lists", () => {
    expect(deduplicateByContent([])).toHaveLength(0);
    expect(deduplicateByContent([{ id: "1", memory: "fact" }])).toHaveLength(1);
  });
});
