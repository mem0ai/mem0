import assert from "node:assert/strict";
import test from "node:test";

import {
  boundedText,
  buildRecallContext,
  createMemoryLifecycle,
  extractConversation,
  redactSecrets,
} from "../src/lifecycle.ts";

test("one lifecycle owns recall state and resets it for a new session", async () => {
  const lifecycle = createMemoryLifecycle({ recallTimeoutMs: 50 });
  const search = async () => ({ results: [{ id: "m1", memory: "Use pnpm" }] });

  assert.match(await lifecycle.recall("package manager", true, search), /Use pnpm/);
  assert.equal(await lifecycle.recall("package manager", true, search), "");

  lifecycle.beginSession();
  assert.match(await lifecycle.recall("package manager", true, search), /Use pnpm/);
});

test("one lifecycle owns capture preparation", () => {
  const lifecycle = createMemoryLifecycle();

  assert.deepEqual(
    lifecycle.prepareConversation([
      { role: "user", content: "password=secret-value" },
      { role: "assistant", content: "Configured it" },
    ]),
    [
      { role: "user", content: "password=[REDACTED]" },
      { role: "assistant", content: "Configured it" },
    ],
  );
});

test("redacts Claude-equivalent credentials before content leaves the host", () => {
  const privateKey = "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----";
  const input = [
    "Authorization: Bearer top-secret-token",
    "api_key=super-secret-value",
    "password=hunter2",
    "ghp_abcdefghijklmnopqrstuvwxyz123456",
    privateKey,
  ].join("\n");

  const output = redactSecrets(input);
  assert.equal(output.includes("top-secret-token"), false);
  assert.equal(output.includes("super-secret-value"), false);
  assert.equal(output.includes("hunter2"), false);
  assert.equal(output.includes("ghp_"), false);
  assert.equal(output.includes("secret\n-----END"), false);
  assert.match(output, /\[REDACTED\]/);
});

test("bounds redacted content and reports the omitted character count", () => {
  assert.equal(boundedText("  abc  ", 10), "abc");
  assert.equal(boundedText("abcdefgh", 5), "abcde\n...[truncated 3 chars]");
});

test("normalizes and sanitizes user/assistant conversation content", () => {
  const messages = [
    { role: "system", content: "ignored" },
    { role: "user", content: [{ type: "text", text: "token=m0-abcdefghijklmnop" }] },
    { role: "assistant", content: [{ type: "tool_use" }, { type: "text", text: "done" }] },
  ];

  assert.deepEqual(extractConversation(messages), [
    { role: "user", content: "token=[REDACTED]" },
    { role: "assistant", content: "done" },
  ]);
});

test("recall is bounded, fail-open, and de-duplicates already injected memories", async () => {
  const seen = new Set<string>(["old"]);
  const search = async () => ({
    results: [
      { id: "old", memory: "already shown" },
      { id: "new", memory: `api_key=hidden ${"x".repeat(100)}` },
    ],
  });

  const output = await buildRecallContext("what changed?", true, search, {
    maxChars: 240,
    seenIds: seen,
  });
  assert.equal(output.includes("already shown"), false);
  assert.equal(output.includes("hidden"), false);
  assert.ok(output.length <= 240);
  assert.equal(seen.has("new"), true);
  assert.equal(
    await buildRecallContext("what changed?", true, async () => {
      throw new Error("offline");
    }),
    "",
  );
});

test("recall times out without blocking the host turn", async () => {
  const never = () => new Promise<{ results?: unknown[] }>(() => {});
  const started = Date.now();

  assert.equal(await buildRecallContext("hello", true, never, { timeoutMs: 5 }), "");
  assert.ok(Date.now() - started < 100);
});
