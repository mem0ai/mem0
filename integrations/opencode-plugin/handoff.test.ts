import {afterEach, describe, expect, mock, test} from "bun:test";
const shared = await import("../agent-plugin-core/typescript/src/handoff.ts");
const actionRun = mock(async (_script: URL, _action: string, _cwd: string, _resource?: string) => "Full historical context");
const run = mock(async (_script: URL, _bundle: unknown) => "Saved shared resource");
mock.module("../agent-plugin-core/typescript/src/handoff.ts", () => ({...shared, runHandoff: run, runHandoffAction: actionRun}));
const {createHandoffTool, activeMessages, registerHandoffCommand} = await import("./handoff");
afterEach(() => {actionRun.mockClear(); run.mockReset(); run.mockResolvedValue("Saved shared resource");});
const user = (id: string, text: string) => ({info: {role: "user", id}, parts: [{type: "text", text}]});
const toolMessage = (id: string, tool = "mem0_handoff") => ({info: {role: "assistant", id, time: {completed: 1}}, parts: [{type: "tool", callID: id, tool, state: {status: "running", input: {}}}]});
function tool(messages: any[]) {
  return createHandoffTool({session: {
    get: async () => ({data: {id: "native", title: "Native task", directory: "/tmp"}}),
    messages: async () => ({data: messages}),
  }} as any);
}
const context = {sessionID: "native", messageID: "handoff", directory: "/tmp/native-project"} as any;
describe("native OpenCode handoff", () => {
  test("exports current full context and skips only its own invocation", async () => {
    const config: any = {};
    registerHandoffCommand(config);
    expect(config.command["mem0-handoff"].template).toContain("$ARGUMENTS");
    expect(await tool([user("u", "x".repeat(20000)), toolMessage("handoff")]).execute({}, context)).toBe("Saved shared resource");
    const bundle = run.mock.calls[0][1] as any;
    expect(bundle.source.session_id).toBe("native");
    expect(bundle.items[0].content[0].text.length).toBe(20000);
    expect(bundle.items).toHaveLength(1);
  });
  test("preserves completed tools and refuses any other unfinished tool", async () => {
    const completed = {info: {role: "assistant", id: "done", time: {completed: 1}}, parts: [{type: "tool", callID: "done", tool: "read", state: {status: "completed", input: {path: "a"}, output: "full result", time: {}}}]};
    await tool([user("u", "task"), completed, toolMessage("handoff")]).execute({}, context);
    expect(JSON.stringify(run.mock.calls[0][1])).toContain("full result");
    await expect(tool([user("u", "task"), toolMessage("other", "read"), toolMessage("handoff")]).execute({}, context)).rejects.toThrow("unfinished");
  });
  test("refuses a different unfinished assistant stream", async () => {
    await expect(tool([user("u", "task"), {info: {role: "assistant", id: "stream", time: {}}, parts: [{type: "text", text: "partial"}]}]).execute({}, context)).rejects.toThrow("unfinished assistant");
  });
  test("rejects a failed assistant response even with a completed timestamp", async () => {
    await expect(tool([user("u", "task"), {
      info: {role: "assistant", id: "failed", time: {completed: 1}, error: {name: "MessageAbortedError", data: {message: "aborted"}}},
      parts: [{type: "text", text: "partial answer"}],
    }]).execute({}, context)).rejects.toThrow("interrupted or failed");
  });
  test("native compaction retains its summary and retained tail, excluding older history", () => {
    const old = user("old", "old context");
    const tail = user("tail", "retained");
    const boundary = {info: {role: "user", id: "c"}, parts: [{type: "compaction", tail_start_id: "tail"}]};
    const summary = {info: {role: "assistant", id: "s", parentID: "c", summary: true, finish: "stop"}, parts: [{type: "text", text: "Summary"}]};
    expect(activeMessages([old, tail, boundary, summary, user("new", "continue")] as any).map(m => m.info.id)).toEqual(["c", "s", "tail", "new"]);
  });
  test("fails on unsupported remote media and propagates importer errors", async () => {
    const image = {info: {role: "user", id: "u"}, parts: [{type: "file", mime: "image/png", url: "https://private/image.png"}]};
    await expect(tool([image]).execute({}, context)).rejects.toThrow("unavailable locally");
    run.mockRejectedValue(new Error("saved at /tmp/retry.json"));
    await expect(tool([user("u", "hi")]).execute({}, context)).rejects.toThrow("saved at /tmp/retry.json");
  });
});

test("list and resume return shared history to the current model using its native project", async () => {
  for (const action of ["list", "resume"] as const) {
    const native = createHandoffTool({session: {get: () => {throw new Error("should not export");}}} as any);
    expect(await native.execute({action, resource: "/tmp/shared task.json"}, context)).toBe("Full historical context");
    expect(actionRun).toHaveBeenLastCalledWith(expect.any(URL), action, "/tmp/native-project", "/tmp/shared task.json");
  }
  expect(run).not.toHaveBeenCalled();
});
