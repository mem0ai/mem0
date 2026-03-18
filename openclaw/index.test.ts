/**
 * Regression tests for per-agent memory isolation helpers and
 * message filtering logic.
 */
import { describe, it, expect } from "vitest";
import {
  extractAgentId,
  effectiveUserId,
  agentUserId,
  resolveUserId,
  isNonInteractiveTrigger,
  isSubagentSession,
  isNoiseMessage,
  isGenericAssistantMessage,
  stripNoiseFromContent,
  filterMessagesForExtraction,
} from "./index.ts";

// ---------------------------------------------------------------------------
// extractAgentId
// ---------------------------------------------------------------------------
describe("extractAgentId", () => {
  it("returns agentId from a named agent session key", () => {
    expect(extractAgentId("agent:researcher:550e8400-e29b")).toBe("researcher");
  });

  it("returns subagent namespace from subagent session key", () => {
    // OpenClaw subagent format: agent:main:subagent:<uuid>
    expect(extractAgentId("agent:main:subagent:3b85177f-69e0-412d-8ecd-fbe542f362ce")).toBe(
      "subagent-3b85177f-69e0-412d-8ecd-fbe542f362ce",
    );
  });

  it("returns undefined for the main agent session (agent:main:main)", () => {
    expect(extractAgentId("agent:main:main")).toBeUndefined();
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
// isNonInteractiveTrigger
// ---------------------------------------------------------------------------
describe("isNonInteractiveTrigger", () => {
  it("returns true for cron trigger", () => {
    expect(isNonInteractiveTrigger("cron", undefined)).toBe(true);
  });

  it("returns true for heartbeat trigger", () => {
    expect(isNonInteractiveTrigger("heartbeat", undefined)).toBe(true);
  });

  it("returns true for automation trigger", () => {
    expect(isNonInteractiveTrigger("automation", undefined)).toBe(true);
  });

  it("returns true for schedule trigger", () => {
    expect(isNonInteractiveTrigger("schedule", undefined)).toBe(true);
  });

  it("is case-insensitive for trigger", () => {
    expect(isNonInteractiveTrigger("CRON", undefined)).toBe(true);
    expect(isNonInteractiveTrigger("Heartbeat", undefined)).toBe(true);
  });

  it("returns false for user-initiated triggers", () => {
    expect(isNonInteractiveTrigger("user", undefined)).toBe(false);
    expect(isNonInteractiveTrigger("webchat", undefined)).toBe(false);
    expect(isNonInteractiveTrigger("telegram", undefined)).toBe(false);
  });

  it("returns false when trigger is undefined and session key is normal", () => {
    expect(isNonInteractiveTrigger(undefined, "agent:main:main")).toBe(false);
  });

  it("detects cron from session key as fallback", () => {
    expect(isNonInteractiveTrigger(undefined, "agent:main:cron:c85abdb2-d900-4cd8-8601-9dd960c560c9")).toBe(true);
  });

  it("detects heartbeat from session key as fallback", () => {
    expect(isNonInteractiveTrigger(undefined, "agent:main:heartbeat:abc123")).toBe(true);
  });

  it("returns false when both trigger and sessionKey are undefined", () => {
    expect(isNonInteractiveTrigger(undefined, undefined)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isSubagentSession
// ---------------------------------------------------------------------------
describe("isSubagentSession", () => {
  it("returns true for subagent session keys", () => {
    expect(isSubagentSession("agent:main:subagent:3b85177f-69e0-412d-8ecd-fbe542f362ce")).toBe(true);
  });

  it("returns false for main agent session", () => {
    expect(isSubagentSession("agent:main:main")).toBe(false);
  });

  it("returns false for named agent session", () => {
    expect(isSubagentSession("agent:researcher:550e8400-e29b")).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(isSubagentSession(undefined)).toBe(false);
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
// isGenericAssistantMessage
// ---------------------------------------------------------------------------
describe("isGenericAssistantMessage", () => {
  it("detects 'I see you've shared' openers", () => {
    expect(isGenericAssistantMessage("I see you've shared an update. How can I help?")).toBe(true);
    expect(isGenericAssistantMessage("I see you've shared a summary of the Atlas configuration update. Is there anything specific you'd like me to help with?")).toBe(true);
  });

  it("detects 'Thanks for sharing' openers", () => {
    expect(isGenericAssistantMessage("Thanks for sharing that update! Would you like me to review the changes?")).toBe(true);
  });

  it("detects 'How can I help' standalone", () => {
    expect(isGenericAssistantMessage("How can I help you with this?")).toBe(true);
  });

  it("detects 'Got it' + follow-up", () => {
    expect(isGenericAssistantMessage("Got it! How can I assist?")).toBe(true);
    expect(isGenericAssistantMessage("Got it. Let me know what you need.")).toBe(true);
  });

  it("detects 'I'll help/review/look into'", () => {
    expect(isGenericAssistantMessage("I'll review that for you.")).toBe(true);
    expect(isGenericAssistantMessage("I'll look into this right away.")).toBe(true);
  });

  it("preserves substantive assistant content", () => {
    expect(isGenericAssistantMessage("## What I Accomplished\n\nDeployed the API to production with Vercel.")).toBe(false);
    expect(isGenericAssistantMessage("The ElevenLabs SDK has been installed and configured. Voice skill is ready.")).toBe(false);
    expect(isGenericAssistantMessage("Updated the call scripts sheet with truth-based messaging templates.")).toBe(false);
  });

  it("preserves long messages even with generic openers", () => {
    const longMsg = "I see you've shared an update. " + "Here are the detailed changes I made to the configuration. ".repeat(10);
    expect(isGenericAssistantMessage(longMsg)).toBe(false);
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

  it("drops generic assistant acknowledgments", () => {
    const messages = [
      { role: "user", content: "[ASSISTANT]: Updated the Google Sheet with truth-based scripts." },
      { role: "assistant", content: "I see you've shared an update. How can I help?" },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].role).toBe("user");
    expect(result[0].content).toContain("Google Sheet");
  });

  it("returns only assistant messages when all user messages are noise", () => {
    // This scenario triggers the #2 guard: no user content remains
    const messages = [
      { role: "user", content: "ok" },
      { role: "user", content: "HEARTBEAT_OK" },
      { role: "assistant", content: "I deployed the API to production." },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(1);
    expect(result[0].role).toBe("assistant");
    // The capture hook checks: if no user messages remain, skip add()
    expect(result.some((m) => m.role === "user")).toBe(false);
  });

  it("keeps substantive assistant messages even with generic opener", () => {
    const messages = [
      { role: "user", content: "What did you do?" },
      { role: "assistant", content: "I deployed the API to production and configured the webhook endpoints for Stripe integration." },
    ];
    const result = filterMessagesForExtraction(messages);
    expect(result).toHaveLength(2);
  });
});

