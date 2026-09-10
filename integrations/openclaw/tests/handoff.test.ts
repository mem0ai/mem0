import { beforeEach, expect, it, vi } from "vitest";
import { runNativeSession } from "../../agent-plugin-core/typescript/src/handoff.ts";
import { registerHandoffCommand } from "../tools/handoff.ts";
vi.mock("../../agent-plugin-core/typescript/src/handoff.ts", () => ({runNativeSession: vi.fn()}));
beforeEach(() => { vi.mocked(runNativeSession).mockReset(); });
function command() {
  const registerCommand = vi.fn();
  registerHandoffCommand({registerCommand} as any);
  return registerCommand.mock.calls[0][0];
}
it("uses the trusted current OpenClaw transcript from a user-only command", async () => {
  const cmd = command();
  expect(cmd.name).toBe("mem0-handoff");
  expect(cmd.requireAuth).toBe(true);
  vi.mocked(runNativeSession).mockResolvedValue("Created Codex task");
  expect(await cmd.handler({args: "codex", sessionFile: "/tmp/native session.jsonl"})).toEqual({text: "Created Codex task"});
  expect(runNativeSession).toHaveBeenCalledWith(expect.any(URL), "openclaw", "/tmp/native session.jsonl");
});
it("fails explicitly on unavailable context or importer errors", async () => {
  const cmd = command();
  expect((await cmd.handler({args: "codex"})).text).toContain("unavailable");
  expect((await cmd.handler({args: "claude"})).text).toContain("Usage:");
  expect(runNativeSession).not.toHaveBeenCalled();
  vi.mocked(runNativeSession).mockRejectedValue(new Error("saved at /tmp/retry.json"));
  expect((await cmd.handler({args: "codex", sessionFile: "/tmp/native.jsonl"})).text).toContain("saved at /tmp/retry.json");
});
