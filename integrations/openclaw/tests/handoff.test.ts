import {afterEach, beforeEach, expect, it, vi} from "vitest";
import {mkdtemp, rm, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {runNativeSession, runHandoffAction} from "../../agent-plugin-core/typescript/src/handoff.ts";
import {registerHandoffCommand} from "../tools/handoff.ts";
vi.mock("../../agent-plugin-core/typescript/src/handoff.ts", async original => ({...await original<typeof import("../../agent-plugin-core/typescript/src/handoff.ts")>(), runNativeSession: vi.fn(), runHandoffAction: vi.fn()}));
let dir: string;
beforeEach(async () => {vi.clearAllMocks(); dir = await mkdtemp(join(tmpdir(), "openclaw-handoff-"));});
afterEach(async () => {await rm(dir, {recursive: true, force: true});});
function setup() {
  const registerCommand = vi.fn();
  const registerTool = vi.fn();
  const hooks = new Map<string, any>();
  registerHandoffCommand({registerCommand, registerTool, on: (name: string, handler: any) => hooks.set(name, handler)} as any);
  return {cmd: registerCommand.mock.calls[0][0], tool: registerTool.mock.calls[0][0]({workspaceDir: "/tmp/native-project"}), hooks};
}
it("saves the trusted current OpenClaw transcript from a user-only command", async () => {
  const {cmd} = setup();
  expect(cmd.name).toBe("mem0-handoff");
  expect(cmd.requireAuth).toBe(true);
  vi.mocked(runNativeSession).mockResolvedValue("Saved shared resource");
  expect(await cmd.handler({sessionFile: "/tmp/native session.jsonl"})).toEqual({text: "Saved shared resource"});
  expect(runNativeSession).toHaveBeenCalledWith(expect.any(URL), "openclaw", "/tmp/native session.jsonl");
});
it("loads resumed history only into the matching native session's next model prompt", async () => {
  const {cmd, hooks} = setup();
  const sessionFile = join(dir, "native.jsonl");
  await writeFile(sessionFile, JSON.stringify({type: "session", cwd: "/tmp/native-project"}) + "\n");
  vi.mocked(runHandoffAction).mockResolvedValue("Full historical context and tools");
  expect((await cmd.handler({args: "resume /tmp/shared task.json", sessionFile, sessionId: "native"})).text).toContain("loaded");
  expect(runHandoffAction).toHaveBeenCalledWith(expect.any(URL), "resume", "/tmp/native-project", "/tmp/shared task.json");
  expect(hooks.get("before_prompt_build")({}, {sessionId: "other"})).toBeUndefined();
  expect(hooks.get("before_prompt_build")({}, {sessionId: "native"})).toEqual({prependContext: "Full historical context and tools"});
  expect(hooks.get("before_prompt_build")({}, {sessionId: "native"})).toBeUndefined();
});
it("clears queued context when the native session ends", async () => {
  const {cmd, hooks} = setup();
  const sessionFile = join(dir, "native.jsonl");
  await writeFile(sessionFile, JSON.stringify({type: "session", cwd: "/tmp"}) + "\n");
  vi.mocked(runHandoffAction).mockResolvedValue("Full historical context");
  await cmd.handler({args: "resume /tmp/shared.json", sessionFile, sessionId: "native"});
  hooks.get("session_end")({sessionId: "native"}, {});
  expect(hooks.get("before_prompt_build")({}, {sessionId: "native"})).toBeUndefined();
});
it("provides a model-visible list/resume tool using only the native workspace", async () => {
  const {tool} = setup();
  vi.mocked(runHandoffAction).mockResolvedValue("Full historical context and tools");
  for (const action of ["list", "resume"]) {
    expect(await tool.execute("call", {action, resource: "/tmp/shared.json", cwd: "/untrusted"})).toEqual({content: [{type: "text", text: "Full historical context and tools"}]});
    expect(runHandoffAction).toHaveBeenLastCalledWith(expect.any(URL), action, "/tmp/native-project", "/tmp/shared.json");
  }
  expect(runNativeSession).not.toHaveBeenCalled();
});
it("fails explicitly on unavailable context or resource errors", async () => {
  const {cmd} = setup();
  expect((await cmd.handler({})).text).toContain("unavailable");
  expect((await cmd.handler({args: "unknown"})).text).toContain("Usage:");
  expect(runNativeSession).not.toHaveBeenCalled();
  vi.mocked(runNativeSession).mockRejectedValue(new Error("invalid native transcript"));
  expect((await cmd.handler({sessionFile: "/tmp/native.jsonl"})).text).toContain("invalid native transcript");
  expect((await cmd.handler({args: "resume /tmp/shared.json", sessionFile: "/tmp/native.jsonl"})).text).toContain("identity is unavailable");
});
