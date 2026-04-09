/**
 * Regression test for #4752 — Feishu channel messages cause mem0 recall to be skipped.
 *
 * openclaw-lark prepends "System: [timestamp] Feishu[...]" to user messages from
 * Feishu channels. The mem0 plugin's `isSystemPrompt` guard was incorrectly treating
 * these as bootstrap/system prompts and skipping recall.
 *
 * This test validates the regex pattern and the full isSystemPrompt logic in isolation
 * (the hook closures are not exported and require the full OpenClaw runtime).
 */
import { describe, it, expect } from "vitest";

/** Regex from openclaw/index.ts — the `isFeishuSystemEvent` guard. */
const feishuSystemEventRe =
  /^system(?:\s*\(untrusted\))?:\s*\[\d{4}-\d{2}-\d{2}.*?\]\s*feishu\[/i;

/** Mirrors the full isSystemPrompt check used inside both hook registrations. */
function isSystemPrompt(prompt: string): boolean {
  const promptLower = prompt.toLowerCase();
  const isFeishuSystemEvent = feishuSystemEventRe.test(prompt);
  return (
    !isFeishuSystemEvent &&
    (promptLower.includes("a new session was started") ||
      promptLower.includes("session startup sequence") ||
      promptLower.includes("/new or /reset") ||
      promptLower.startsWith("system:") ||
      promptLower.startsWith("run your session"))
  );
}

describe("Feishu system event prompt detection (#4752)", () => {
  it("does NOT classify Feishu channel messages as system prompts", () => {
    const feishuMessages = [
      'System: [2026-04-08 10:00:00 GMT+8] Feishu[direct:ou_abc] 吴总: 你好',
      "System: [2026-04-09 11:19 GMT+8] Feishu[group:oc_123] SomeUser: hello world",
      "System (untrusted): [2026-04-09 12:00:00 GMT+8] Feishu[direct:ou_xyz] test",
      'system: [2026-01-01 00:00:00 GMT+0] Feishu[direct:x] user: test', // lowercase
    ];
    for (const msg of feishuMessages) {
      expect(isSystemPrompt(msg)).toBe(false);
    }
  });

  it("still classifies actual system/bootstrap prompts as system prompts", () => {
    const systemMessages = [
      "system: a new session was started",
      "System: session startup sequence",
      "System: /new or /reset",
      "system: run your session configuration",
      "system: please load the bootstrap",
    ];
    for (const msg of systemMessages) {
      expect(isSystemPrompt(msg)).toBe(true);
    }
  });

  it("does not match Feishu-like text that is NOT a system event", () => {
    // Regular user message mentioning Feishu — no "System:" prefix
    expect(isSystemPrompt("Can you check Feishu[direct:abc]?")).toBe(false);
  });

  it("does not match bare system: prompts without the Feishu pattern", () => {
    expect(isSystemPrompt("system: some random system instruction")).toBe(true);
    expect(isSystemPrompt("system: please help with code")).toBe(true);
  });

  it("handles edge cases: no timestamp, no Feishu bracket", () => {
    // No timestamp after "System:" — should NOT match the Feishu regex
    expect(feishuSystemEventRe.test("system: Feishu[something]")).toBe(false);
    // Valid format with minimal timestamp
    expect(
      feishuSystemEventRe.test("System: [2026-04-09] Feishu[direct:x]"),
    ).toBe(true);
    // Timestamp but no Feishu — should NOT match
    expect(
      feishuSystemEventRe.test("system: [2026-04-09 12:00] something else"),
    ).toBe(false);
  });
});
