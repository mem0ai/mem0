import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";
import { buildHandoffBundle, runNativeSession, runHandoff, runHandoffAction, parseHandoffArgs } from "../src/handoff.ts";
const source = {host: "test", session_id: "native", title: "Native title", cwd: "/tmp"};

test("native context preserves summary, full tools/images, excludes only triggering call, rejects loss", async () => {
  const messages = [
    {role: "user", content: "Readable compaction summary"},
    {role: "assistant", content: [{type: "thinking", thinking: "private"}, {type: "toolCall", id: "call", name: "read", arguments: {path: "x"}}]},
    {role: "toolResult", toolCallId: "call", content: [{type: "text", text: "x".repeat(20000)}, {type: "image", data: "aGVsbG8=", mimeType: "image/png"}]},
    {role: "assistant", content: [{type: "toolCall", id: "handoff", name: "mem0_handoff", arguments: {}}]},
  ];
  const bundle = await buildHandoffBundle(source, messages, {excludeCallId: "handoff"});
  assert.equal(bundle.items.length, 3);
  assert.equal((bundle.items[2].output as any[])[0].text.length, 20000);
  assert.equal((bundle.items[2].output as any[])[1].source.data, "aGVsbG8=");
  assert.equal(bundle.source.title, "Native title");
  assert.match(bundle.warnings[0], /reasoning/);
  await assert.rejects(buildHandoffBundle(source, messages), /unfinished/);
  await assert.rejects(buildHandoffBundle(source, [{role: "user", content: [{type: "opaque-compaction"}]}]), /Unsupported/);
  await assert.rejects(buildHandoffBundle(source, [{role: "toolResult", toolCallId: "missing", content: "x"}]), /missing/);
  const deepseek = await buildHandoffBundle(source, [
    {role: "user", content: "hi"},
    {role: "assistant", content: [{type: "tool-call", id: "d", name: "cmd", arguments: "{}"}]},
    {role: "user", content: [{type: "tool-result", toolCallId: "d", isError: true, content: [{type: "text", text: "failed"}]}]},
  ]);
  assert.deepEqual((deepseek.items[2].output as any[])[0], {type: "text", text: "[Tool error]"});
});

test("transport sends native bundle on stdin and native arguments literally", async () => {
  const dir = await mkdtemp(join(tmpdir(), "mem0-handoff-"));
  const script = join(dir, "importer.py");
  try {
    await writeFile(script, "import json, sys\nprint(json.dumps(sys.argv[1:]))\n");
    const session = "--session with spaces; $(touch should-never-exist)";
    const args = JSON.parse(await runNativeSession(pathToFileURL(script), "openclaw", session));
    assert.deepEqual(args, ["--save", "--source=openclaw", `--session=${session}`, "--command-output"]);
    assert.throws(() => runNativeSession(pathToFileURL(script), "openclaw", " "), /session path/);
    await writeFile(script, "import json, sys\nprint(json.dumps(json.load(sys.stdin)))\n");
    const bundle = await buildHandoffBundle(source, [{role: "user", content: "private session"}]);
    assert.deepEqual(JSON.parse(await runHandoff(pathToFileURL(script), bundle)), bundle);
    await writeFile(script, "import sys\nprint('handoff failed: saved at /tmp/retry.json', file=sys.stderr)\nsys.exit(1)\n");
    await assert.rejects(runHandoff(pathToFileURL(script), bundle), /saved at \/tmp\/retry.json/);
  } finally { await rm(dir, {recursive: true, force: true}); }
});


test("native assistant completion metadata cannot be lost during translation", async () => {
  const user = {role: "user", content: "Continue this task"};
  const partial = {role: "assistant", content: "Unfinished answer"};
  for (const metadata of [
    {stopReason: "aborted"}, {stopReason: "error"}, {finishReason: "interrupted"},
    {status: "in_progress"}, {status: "incomplete"}, {partial: true},
    {finishReason: {kind: "error"}}, {stop_reason: "aborted"},
  ]) {
    await assert.rejects(buildHandoffBundle(source, [user, {...partial, ...metadata}]), /incomplete|interrupted/);
  }
  const invocation = {role: "assistant", status: "in_progress", content: [
    {type: "toolCall", id: "handoff", name: "mem0_handoff", arguments: {}},
  ]};
  const bundle = await buildHandoffBundle(source, [user, invocation], {excludeCallId: "handoff"});
  assert.equal(bundle.items.length, 1);
  await assert.rejects(buildHandoffBundle(source, [user, invocation], {excludeCallId: "different"}), /incomplete|interrupted/);
  await assert.rejects(buildHandoffBundle(source, [user, {...invocation, stopReason: "aborted"}], {excludeCallId: "handoff"}), /incomplete|interrupted/);
  await assert.rejects(buildHandoffBundle(source, [user, invocation, {...partial, status: "incomplete"}], {excludeCallId: "handoff"}), /incomplete|interrupted/);
  assert.equal((await buildHandoffBundle(source, [user, {...partial, stopReason: "stop"}])).items.length, 2);
});


test("missing native tool IDs cannot match an absent invocation exclusion", async () => {
  const user = {role: "user", content: "task"};
  const call = {role: "assistant", content: [{type: "toolCall", name: "read", arguments: {}}]};
  await assert.rejects(buildHandoffBundle(source, [user, call]), /Tool call ID/);
  await assert.rejects(buildHandoffBundle(source, [user], {excludeCallId: ""}), /Excluded handoff call ID/);
});

test("shared resource actions preserve literal paths and deliver full historical data", async () => {
  assert.deepEqual(parseHandoffArgs(), {action: "save"});
  assert.deepEqual(parseHandoffArgs("resume /tmp/my resource.json"), {action: "resume", resource: "/tmp/my resource.json"});
  assert.throws(() => parseHandoffArgs("resume"), /Usage/);
  const dir = await mkdtemp(join(tmpdir(), "mem0-resume-"));
  const script = join(dir, "resource.py");
  try {
    await writeFile(script, "import json, sys\nprint(json.dumps(sys.argv[1:]))\n");
    assert.deepEqual(JSON.parse(await runHandoffAction(pathToFileURL(script), "list", "/tmp/native repo")), ["--list", "--cwd=/tmp/native repo", "--command-output"]);
    await assert.rejects(runHandoffAction(pathToFileURL(script), "resume", "/tmp"), /resource path/);
    await assert.rejects(runHandoffAction(pathToFileURL(script), "resume", "/tmp", "x"), /Invalid handoff/);
    const history = {context_type: "historical_session", resource: "/tmp/shared.json", handoff: await buildHandoffBundle(source, [{role: "user", content: "x".repeat(100000)}])};
    await writeFile(script, `import json, sys\nassert sys.argv[1:] == ["--resume=--file $(touch no) name.json", "--cwd=/tmp/native repo", "--command-output"]\nprint(${JSON.stringify(JSON.stringify(history))})\n`);
    const output = await runHandoffAction(pathToFileURL(script), "resume", "/tmp/native repo", "--file $(touch no) name.json");
    assert.match(output, /historical data/);
    assert.match(output, /do not automatically re-execute/);
    assert.ok(output.endsWith(JSON.stringify(history)));
  } finally { await rm(dir, {recursive: true, force: true}); }
});
