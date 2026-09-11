import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import mem0Extension from "./entry.ts";
import {buildSessionContext, convertToLlm} from "@earendil-works/pi-coding-agent";
import {runHandoff, runHandoffAction} from "../../agent-plugin-core/typescript/src/handoff.ts";
vi.mock("../../agent-plugin-core/typescript/src/handoff.ts", async (original) => ({...await original<typeof import("../../agent-plugin-core/typescript/src/handoff.ts")>(), runHandoff: vi.fn(), runHandoffAction: vi.fn()}));
vi.mock("@earendil-works/pi-coding-agent", () => ({
  buildSessionContext: vi.fn(() => ({messages: [{role: "user", content: "Native summary and retained tail"}]})),
  convertToLlm: vi.fn(messages => messages),
}));
vi.mock("./config/index.ts", () => ({loadConfig: () => ({apiKey: ""}), CONFIG_DIR: "/tmp/mem0-pi-handoff-tests"}));
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("process", {...process, versions: {...process.versions, node: "22.19.0"}});
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function setup() {
  const commands = new Map<string, any>();
  const pi = {registerCommand: vi.fn((name, command) => commands.set(name, command)), sendMessage: vi.fn()};
  const entries = [
    {type: "message", id: "old", parentId: null, message: {role: "user", content: "old context"}},
    {type: "message", id: "keep", parentId: "old", message: {role: "user", content: "retained tail"}},
    {type: "compaction", id: "compact", parentId: "keep", summary: "Native summary", firstKeptEntryId: "keep", tokensBefore: 100},
    {type: "message", id: "new", parentId: "compact", message: {role: "user", content: "Continue this task"}},
  ];
  const ctx = {ui: {notify: vi.fn()}, isIdle: () => true, sessionManager: {
    getEntries: () => entries, getLeafId: () => "new", getSessionId: () => "pi-native",
    getSessionName: () => "My Pi task", getCwd: () => "/tmp", getSessionFile: () => "/tmp/pi.jsonl",
  }};
  vi.spyOn(console, "warn").mockImplementation(() => {});
  mem0Extension(pi as any);
  return {pi, ctx, handler: commands.get("mem0-handoff").handler};
}
describe("native Pi handoff", () => {
  it("keeps startup working on Node 20 and explains the native handoff runtime requirement", async () => {
    vi.stubGlobal("process", {...process, versions: {...process.versions, node: "20.20.2"}});
    const {ctx, handler} = setup();
    await handler("save", ctx);
    expect(ctx.ui.notify).toHaveBeenCalledWith(expect.stringContaining("Node.js 22.19+"), "error");
    expect(buildSessionContext).not.toHaveBeenCalled();
    expect(runHandoff).not.toHaveBeenCalled();
  });
  it("uses host compaction/branch selection and the current session without a Mem0 key", async () => {
    const {pi, ctx, handler} = setup();
    vi.mocked(runHandoff).mockResolvedValue("Saved shared resource");
    await handler("save", ctx);
    expect(buildSessionContext).toHaveBeenCalledWith(ctx.sessionManager.getEntries(), "new");
    expect(convertToLlm).toHaveBeenCalledOnce();
    const bundle = vi.mocked(runHandoff).mock.calls[0][1];
    expect(bundle.source).toMatchObject({host: "pi-agent", session_id: "pi-native", title: "My Pi task"});
    expect(JSON.stringify(bundle.items)).toContain("Native summary");
    expect(JSON.stringify(bundle.items)).toContain("retained tail");
    expect(JSON.stringify(bundle.items)).not.toContain("old context");
    expect(pi.sendMessage).toHaveBeenCalledWith({customType: "mem0-handoff", content: "Saved shared resource", display: true});
  });
  it.each(["resume", "save session-id", "claude"])("rejects unsupported arguments %s", async (args) => {
    const {ctx, handler} = setup();
    await handler(args, ctx);
    expect(runHandoff).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(expect.stringContaining("Usage:"), "error");
  });
  it("reports an active response or importer failure", async () => {
    const {pi, ctx, handler} = setup();
    await handler("save", {...ctx, isIdle: () => false});
    expect(runHandoff).not.toHaveBeenCalled();
    vi.mocked(runHandoff).mockRejectedValue(new Error("saved at /tmp/retry.json"));
    await handler("save", ctx);
    expect(ctx.ui.notify).toHaveBeenCalledWith("saved at /tmp/retry.json", "error");
    expect(pi.sendMessage).not.toHaveBeenCalled();
  });
});

it.each(["list", "resume /tmp/shared task.json"])("supports %s on Node 20 without loading native export helpers", async (args) => {
  vi.stubGlobal("process", {...process, versions: {...process.versions, node: "20.20.2"}});
  const {pi, ctx, handler} = setup();
  vi.mocked(runHandoffAction).mockResolvedValue("Full historical user, assistant and tool context");
  await handler(args, ctx);
  const resume = args.startsWith("resume");
  expect(runHandoffAction).toHaveBeenCalledWith(expect.any(URL), resume ? "resume" : "list", "/tmp", resume ? "/tmp/shared task.json" : undefined);
  expect(pi.sendMessage).toHaveBeenCalledWith({customType: "mem0-handoff", content: "Full historical user, assistant and tool context", display: true}, {triggerTurn: resume});
  expect(buildSessionContext).not.toHaveBeenCalled();
  expect(runHandoff).not.toHaveBeenCalled();
});
