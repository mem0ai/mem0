import assert from "node:assert/strict";
import test from "node:test";

import {
  boundedText,
  buildRecallContext,
  createMemoryLifecycle,
  extractConversation,
  redactSecrets,
  repoCaptureOptions,
  type ConversationMessage,
} from "../src/lifecycle.ts";

test("recall searches once for the first prompt and keeps that context for the session", async () => {
  const lifecycle = createMemoryLifecycle({ recallTimeoutMs: 50 });
  const queries: string[] = [];
  const search = async (query: string) => {
    queries.push(query);
    return { results: [{ id: "m1", memory: "Use pnpm" }] };
  };

  const first = await lifecycle.recall("which package manager does this repo use?", true, search);
  assert.match(first, /1\. Use pnpm/);
  assert.equal(await lifecycle.recall("a different second prompt entirely", true, search), first);
  assert.equal(queries.length, 1);

  lifecycle.beginSession();
  assert.equal(await lifecycle.recall("too short", true, search), "");
  assert.equal(await lifecycle.recall("a longer prompt that would have searched", true, search), "");
  assert.equal(queries.length, 1);
});

test("capture checkpoints end on an assistant response and flush the rest when forced", () => {
  const lifecycle = createMemoryLifecycle();
  for (let turn = 1; turn <= 6; turn++) {
    lifecycle.recordUserPrompt(`prompt ${turn}`);
    if (turn === 1) assert.deepEqual(lifecycle.takeCheckpoint(), []);
    lifecycle.recordAssistantResponse(turn === 1 ? "api_key=hidden" : `answer ${turn}`);
  }
  lifecycle.recordAssistantResponse("   ");

  const due = lifecycle.takeCheckpoint();
  assert.equal(due.length, 10);
  assert.deepEqual(due.slice(0, 2), [
    { role: "user", content: "prompt 1" },
    { role: "assistant", content: "api_key=[REDACTED]" },
  ]);
  assert.deepEqual(lifecycle.takeCheckpoint(), []);
  assert.deepEqual(lifecycle.takeCheckpoint(true), [
    { role: "user", content: "prompt 6" },
    { role: "assistant", content: "answer 6" },
  ]);
  assert.deepEqual(lifecycle.takeCheckpoint(true), []);

  lifecycle.recordUserPrompt("x".repeat(40_000));
  lifecycle.recordAssistantResponse("done");
  assert.equal(lifecycle.takeCheckpoint().length, 2);
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

test("capture preserves long prompts and responses while redacting secrets", () => {
  const lifecycle = createMemoryLifecycle();
  const prompt = "Repository question. ".repeat(2000) + "Final requirement. api_key=hidden-user-secret";
  const answer = "Repository answer. ".repeat(4000) + "Final detail. password=hidden-agent-secret";
  assert.deepEqual(lifecycle.prepareConversation([
    { role: "user", content: prompt },
    { role: "assistant", content: [{ type: "text", text: answer }] },
  ]), [
    { role: "user", content: redactSecrets(prompt) },
    { role: "assistant", content: redactSecrets(answer) },
  ]);
  assert.equal(lifecycle.prepareUserText(prompt), redactSecrets(prompt));
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

test("recall matches Claude Code formatting, bounds output, and fails open", async () => {
  const search = async () => ({
    results: [
      { id: "episode", memory: "raw episode", metadata: { record_kind: "task_episode" } },
      { id: "a", memory: "Uses   pnpm\nworkspaces", metadata: { branch: "main" } },
      { id: "b", memory: "Adds retries", metadata: { branch: "feat/retry" } },
    ],
  });
  assert.equal(
    await buildRecallContext("what changed?", true, search),
    [
      "<mem0-relevant-memories>",
      "Mem0 found these relevant memories from earlier work in this repository:",
      "1. Uses pnpm workspaces",
      "2. Adds retries [learnt on branch feat/retry]",
      "</mem0-relevant-memories>",
    ].join("\n"),
  );

  const long = async () => ({ results: [{ id: "n", memory: `api_key=hidden ${"x".repeat(500)}` }] });
  const output = await buildRecallContext("what changed?", true, long, { maxChars: 240 });
  assert.equal(output.includes("hidden"), false);
  assert.match(output, /…\n<\/mem0-relevant-memories>$/);
  assert.equal(output.length, 240);
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

test("after a response, due checkpoints send now and anything else waits for the forced flush", async () => {
  const lifecycle = createMemoryLifecycle();
  const sent: [number, string][] = [];
  const send = async (batch: ConversationMessage[], reason: string) => void sent.push([batch.length, reason]);

  lifecycle.recordUserPrompt("prompt");
  lifecycle.recordAssistantResponse("answer");
  await lifecycle.afterResponse(send);
  assert.deepEqual(sent, []);

  for (let turn = 2; turn <= 5; turn++) {
    lifecycle.recordUserPrompt(`prompt ${turn}`);
    lifecycle.recordAssistantResponse(`answer ${turn}`);
  }
  await lifecycle.afterResponse(send);
  assert.deepEqual(sent, [[10, "periodic"]]);

  lifecycle.recordUserPrompt("last prompt");
  await lifecycle.end("session-end", send);
  assert.deepEqual(sent, [
    [10, "periodic"],
    [1, "session-end"],
  ]);
});

test("capture options put repository facts in the project lane and omit unknown git facts", () => {
  const repo = { appId: "mem0ai-mem0", projectId: "mem0ai-mem0-abc", projectIds: [], branch: "", sha: "", dirs: ["src"] };
  const options = repoCaptureOptions(repo, "alice", "s1", "opencode");
  assert.deepEqual(
    { ...options, agent_custom_instructions: undefined, custom_instructions: undefined, custom_categories: undefined },
    {
      agent_id: "mem0ai-mem0-abc",
      user_id: "alice",
      app_id: "mem0ai-mem0",
      run_id: "s1",
      metadata: { source: "opencode", author: "alice", dirs: ["src"] },
      agent_custom_instructions: undefined,
      custom_instructions: undefined,
      custom_categories: undefined,
      infer: true,
    },
  );
  assert.deepEqual(repoCaptureOptions({ ...repo, branch: "main", sha: "f00" }, "alice", "s1", "pi").metadata, {
    source: "pi",
    branch: "main",
    git_sha: "f00",
    author: "alice",
    dirs: ["src"],
  });
});
