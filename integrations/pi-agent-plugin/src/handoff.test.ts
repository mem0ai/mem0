import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import mem0Extension from "./entry.ts";
import {runHandoff} from "../../agent-plugin-core/typescript/src/handoff.ts";
vi.mock("../../agent-plugin-core/typescript/src/handoff.ts", async (original) => ({...await original<typeof import("../../agent-plugin-core/typescript/src/handoff.ts")>(), runHandoff: vi.fn()}));
vi.mock("./config/index.ts", () => ({loadConfig: () => ({apiKey: ""}), CONFIG_DIR: "/tmp/mem0-pi-handoff-tests"}));
beforeEach(() => { vi.clearAllMocks(); });
afterEach(() => vi.restoreAllMocks());
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
  it("uses host compaction/branch selection and the current session without a Mem0 key", async () => {
    const {pi, ctx, handler} = setup();
    vi.mocked(runHandoff).mockResolvedValue("Created Codex task");
    await handler("codex", ctx);
    const bundle = vi.mocked(runHandoff).mock.calls[0][1];
    expect(bundle.source).toMatchObject({host: "pi-agent", session_id: "pi-native", title: "My Pi task"});
    expect(JSON.stringify(bundle.items)).toContain("Native summary");
    expect(JSON.stringify(bundle.items)).toContain("retained tail");
    expect(JSON.stringify(bundle.items)).not.toContain("old context");
    expect(pi.sendMessage).toHaveBeenCalledWith({customType: "mem0-handoff", content: "Created Codex task", display: true});
  });
  it.each(["", "codex session-id", "claude"])("rejects unsupported arguments %s", async (args) => {
    const {ctx, handler} = setup();
    await handler(args, ctx);
    expect(runHandoff).not.toHaveBeenCalled();
    expect(ctx.ui.notify).toHaveBeenCalledWith(expect.stringContaining("Usage:"), "warning");
  });
  it("reports an active response or importer failure", async () => {
    const {pi, ctx, handler} = setup();
    await handler("codex", {...ctx, isIdle: () => false});
    expect(runHandoff).not.toHaveBeenCalled();
    vi.mocked(runHandoff).mockRejectedValue(new Error("saved at /tmp/retry.json"));
    await handler("codex", ctx);
    expect(ctx.ui.notify).toHaveBeenCalledWith("saved at /tmp/retry.json", "error");
    expect(pi.sendMessage).not.toHaveBeenCalled();
  });
});
