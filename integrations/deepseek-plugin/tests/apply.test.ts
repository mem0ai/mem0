import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Offline mock of the Mem0 SDK so these tests never touch the network.
vi.mock("../../agent-plugin-core/typescript/src/handoff.ts", async (original) => ({
  ...await original<typeof import("../../agent-plugin-core/typescript/src/handoff.ts")>(), runHandoff: vi.fn(), runHandoffAction: vi.fn(),
}));
import { runHandoff, runHandoffAction } from "../../agent-plugin-core/typescript/src/handoff.ts";

const mockSearch = vi.fn();
const mockAdd = vi.fn();
vi.mock("mem0ai", () => ({
  MemoryClient: class {
    search = mockSearch;
    add = mockAdd;
  },
}));

// The real `@deepseek-ai/dsh-tools` runtime transitively imports harness peer
// packages the host provides at runtime but which aren't installed here. For
// these unit tests we only need `defineTool` to hand back the definition it was
// given, so the registered tool's `execute`/`name` can be exercised directly.
vi.mock("@deepseek-ai/dsh-tools", () => ({
  defineTool: (options: unknown) => options,
}));

import { apply, type Config } from "../src/index.ts";

interface RegisteredTool {
  name: string;
  execute(args: unknown, exec: unknown): Promise<unknown>;
}

type HarnessListener = (...args: any[]) => unknown;

function applyAndCollect(config: Config, attachments?: unknown): Map<string, RegisteredTool> {
  const tools = new Map<string, RegisteredTool>();
  const ctx = {
    tools: { register: (t: RegisteredTool) => tools.set(t.name, t) },
    get: (service: string) => service === "attachments" ? attachments : undefined,
    get attachments() { throw new Error('cannot get property "attachments" without inject'); },
    on: vi.fn(),
  };
  apply(ctx as never, config);
  return tools;
}

function applyAndCollectListeners(config: Config): Map<string, HarnessListener> {
  const listeners = new Map<string, HarnessListener>();
  const ctx = {
    tools: { register: vi.fn() },
    on: (event: string, listener: HarnessListener) => listeners.set(event, listener),
  };
  apply(ctx as never, config);
  return listeners;
}

let savedKey: string | undefined;
let savedTelemetry: string | undefined;

beforeEach(() => {
  savedKey = process.env.MEM0_API_KEY;
  savedTelemetry = process.env.MEM0_TELEMETRY;
  process.env.MEM0_TELEMETRY = "false";
  vi.mocked(runHandoff).mockReset();
  mockSearch.mockReset();
  mockAdd.mockReset();
});

afterEach(() => {
  if (savedKey === undefined) delete process.env.MEM0_API_KEY;
  else process.env.MEM0_API_KEY = savedKey;
  if (savedTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
  else process.env.MEM0_TELEMETRY = savedTelemetry;
});

describe("apply() config validation", () => {
  it("keeps local handoff available without a Mem0 key", () => {
    delete process.env.MEM0_API_KEY;
    expect([...applyAndCollect({ userId: "u" }).keys()]).toEqual(["mem0_handoff"]);
  });

  it("throws when userId is missing", () => {
    expect(() => applyAndCollect({ apiKey: "k", userId: "" } as Config)).toThrow(/userId/);
  });

  it("registers memory and handoff tools", () => {
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });
    expect([...tools.keys()].sort()).toEqual(["add_memory", "mem0_handoff", "search_memory"]);
  });
});

describe("Harness lifecycle", () => {
  it("automatically recalls memory into the prompt for the latest human message", async () => {
    mockSearch.mockResolvedValue({
      results: [{ id: "m1", memory: "Likes tea" }],
    });
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const assemble = listeners.get("system-prompt/assemble")!;
    const base = { sections: [], contexts: [], tools: [], variables: {} };

    const result = await assemble(
      base,
      {
        agent: {
          session: {
            deriveMessages: () => [
              {
                role: "user",
                content: [{ type: "text", text: "What do I drink?" }],
                source: { kind: "user" },
              },
            ],
          },
        },
      },
      async () => base,
    );

    expect(mockSearch).toHaveBeenCalledWith("What do I drink?", {
      filters: { user_id: "u" },
      topK: 5,
    });
    expect(result).toMatchObject({
      contexts: [{ name: "mem0:recall", text: expect.stringContaining("Likes tea") }],
    });
  });

  it("automatically captures a completed human and assistant turn", async () => {
    mockAdd.mockResolvedValue({ eventId: "evt-1", status: "PENDING" });
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const onSessionEvent = listeners.get("session/event")!;
    const session = {};

    onSessionEvent(session, { type: "turn/start", data: { turn: 1 } });
    onSessionEvent(session, {
      type: "user/message",
      data: {
        role: "user",
        content: [{ type: "text", text: "Remember I like tea" }],
        source: { kind: "user" },
      },
    });
    onSessionEvent(session, {
      type: "assistant/message",
      data: {
        turn: 1,
        message: {
          role: "assistant",
          content: [{ type: "text", text: "I will remember that." }],
          source: { kind: "model" },
        },
      },
    });
    onSessionEvent(session, {
      type: "turn/end",
      data: { turn: 1, reason: { kind: "completed" } },
    });

    await vi.waitFor(() => {
      expect(mockAdd).toHaveBeenCalledWith(
        [
          { role: "user", content: "Remember I like tea" },
          { role: "assistant", content: "I will remember that." },
        ],
        { userId: "u", source: "DEEPSEEK_HARNESS" },
      );
    });
  });

  it("can disable automatic recall and capture without removing the memory tools", () => {
    const listeners = applyAndCollectListeners({
      apiKey: "k",
      userId: "u",
      autoRecall: false,
      autoCapture: false,
    });

    expect(listeners.has("system-prompt/assemble")).toBe(false);
    expect(listeners.has("session/event")).toBe(false);
  });
});

describe("search_memory tool", () => {
  it("returns a formatted list scoped to the configured user", async () => {
    mockSearch.mockResolvedValue({
      results: [{ id: "m1", memory: "Likes tea", categories: ["preference"] }],
    });
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("search_memory")!.execute({ query: "drink" }, {});

    expect(out).toContain("Likes tea");
    expect(out).toContain("[mem0:m1]");
    expect(mockSearch).toHaveBeenCalledWith("drink", {
      filters: { user_id: "u" },
      topK: 10,
    });
  });

  it("honors a per-call userId override and limit", async () => {
    mockSearch.mockResolvedValue({ results: [] });
    const tools = applyAndCollect({ apiKey: "k", userId: "u", allowUserOverride: true });

    await tools.get("search_memory")!.execute({ query: "x", userId: "alice", limit: 3 }, {});

    expect(mockSearch).toHaveBeenCalledWith("x", {
      filters: { user_id: "alice" },
      topK: 3,
    });
  });

  it("returns a graceful failure line instead of rejecting on error", async () => {
    mockSearch.mockRejectedValue(new Error("network down"));
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("search_memory")!.execute({ query: "x" }, {});

    expect(out).toContain("search_memory failed");
    expect(out).toContain("network down");
  });
});

describe("add_memory tool", () => {
  it("reports the write as queued on the async PENDING response, with camelCase scope + source", async () => {
    // The real /v3/memories/add/ response — not an array of memories. The SDK
    // camel-cases response keys, so it surfaces as `eventId`, not `event_id`.
    mockAdd.mockResolvedValue({ eventId: "evt-123", status: "PENDING" });
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("add_memory")!.execute({ text: "remember this" }, {});

    expect(out).toContain("queued");
    expect(out).toContain("evt-123");
    expect(out).not.toContain("No new distinct memory");
    expect(mockAdd).toHaveBeenCalledWith(
      [{ role: "user", content: "remember this" }],
      { userId: "u", source: "DEEPSEEK_HARNESS" },
    );
  });

  it("renders a list when the backend returns memories", async () => {
    mockAdd.mockResolvedValue([{ id: "m1", memory: "Fact" }]);
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("add_memory")!.execute({ text: "x" }, {});

    expect(out).toContain("Stored 1 memory");
    expect(out).toContain("[mem0:m1]");
  });

  it("redacts credentials before storing explicit memory", async () => {
    mockAdd.mockResolvedValue([]);
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    await tools.get("add_memory")!.execute({ text: "api_key=do-not-store-this" }, {});

    expect(mockAdd).toHaveBeenCalledWith(
      [{ role: "user", content: "api_key=[REDACTED]" }],
      { userId: "u", source: "DEEPSEEK_HARNESS" },
    );
  });

  it("returns a graceful failure line on error", async () => {
    mockAdd.mockRejectedValue(new Error("boom"));
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("add_memory")!.execute({ text: "x" }, {});

    expect(out).toContain("add_memory failed");
    expect(out).toContain("boom");
  });
});

describe("tool user ownership", () => {
  it("rejects cross-user reads and writes before contacting Mem0", async () => {
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });
    await expect(tools.get("search_memory")!.execute({ query: "x", userId: "other" }, {})).rejects.toThrow(/allowUserOverride/);
    await expect(tools.get("add_memory")!.execute({ text: "x", userId: "other" }, {})).rejects.toThrow(/allowUserOverride/);
    expect(mockSearch).not.toHaveBeenCalled();
    expect(mockAdd).not.toHaveBeenCalled();
  });
});


describe("mem0_handoff tool", () => {
  const exec = {callId: "handoff", agent: {session: {
    id: "native-session", header: {cwd: "/tmp"},
    events: [{type: "session/title", data: {title: "Old title"}}, {type: "session/title", data: {title: "Renamed native task"}}],
    deriveMessages: () => [
      {role: "user", content: [{type: "text", text: "Readable current context"}]},
      {role: "assistant", content: [{type: "tool-call", id: "handoff", name: "mem0_handoff", arguments: "{}"}]},
    ],
  }}};
  it("exports the current native session, excluding only its own in-flight call", async () => {
    vi.mocked(runHandoff).mockResolvedValue("Saved shared resource");
    const tools = applyAndCollect({apiKey: "k", userId: "u"});
    expect(await tools.get("mem0_handoff")!.execute({}, exec)).toBe("Saved shared resource");
    expect(runHandoff).toHaveBeenCalledWith(expect.any(URL), expect.objectContaining({
      source: expect.objectContaining({host: "deepseek", session_id: "native-session", title: "Renamed native task"}),
      items: [{type: "message", role: "user", content: [{type: "input_text", text: "Readable current context"}]}],
    }));
    expect(mockSearch).not.toHaveBeenCalled();
    expect(mockAdd).not.toHaveBeenCalled();
  });
  it.each(["list", "resume"])("%s consumes shared resources in the active model without exporting its session", async (action) => {
    delete process.env.MEM0_API_KEY;
    vi.mocked(runHandoffAction).mockResolvedValue("Complete historical context and tool outcomes");
    const tools = applyAndCollect({userId: "u"});
    expect(await tools.get("mem0_handoff")!.execute({action, resource: "/tmp/shared task.json"}, exec)).toBe("Complete historical context and tool outcomes");
    expect(runHandoffAction).toHaveBeenCalledWith(expect.any(URL), action, "/tmp", "/tmp/shared task.json");
    expect(runHandoff).not.toHaveBeenCalled();
    expect(mockSearch).not.toHaveBeenCalled();
    expect(mockAdd).not.toHaveBeenCalled();
  });
  it("reads native image bytes through Cordis optional service lookup", async () => {
    const readImage = vi.fn(async () => ({ref: {mediaType: "image/png"}, data: new Uint8Array([104,105])}));
    const tools = applyAndCollect({apiKey: "k", userId: "u"}, {readImage});
    const imageExec = {...exec, agent: {session: {...exec.agent.session, deriveMessages: () => [
      {role: "user", content: [{type: "text", text: "Describe this image"}, {type: "image", attachment: {id: "native-image"}}]},
    ]}}};
    vi.mocked(runHandoff).mockResolvedValue("Saved image context");
    expect(await tools.get("mem0_handoff")!.execute({}, imageExec)).toBe("Saved image context");
    expect(readImage).toHaveBeenCalledWith({id: "native-image"});
    expect(JSON.stringify(vi.mocked(runHandoff).mock.calls[0][1])).toContain("data:image/png;base64,aGk=");
    const unavailable = applyAndCollect({apiKey: "k", userId: "u"});
    expect(await unavailable.get("mem0_handoff")!.execute({}, imageExec)).toContain("attachment storage is unavailable");
  });
  it("refuses unfinished sibling tools rather than hiding them with its own invocation", async () => {
    const tools = applyAndCollect({apiKey: "k", userId: "u"});
    const siblingExec = {...exec, agent: {session: {...exec.agent.session, deriveMessages: () => [
      ...exec.agent.session.deriveMessages(),
      {role: "assistant", content: [{type: "tool-call", id: "other", name: "read", arguments: "{}"}]},
    ]}}};
    expect(await tools.get("mem0_handoff")!.execute({}, siblingExec)).toContain("unfinished");
    expect(runHandoff).not.toHaveBeenCalled();
  });
  it("reports unavailable native state and importer failures", async () => {
    const tools = applyAndCollect({apiKey: "k", userId: "u"});
    expect(await tools.get("mem0_handoff")!.execute({}, {})).toContain("unavailable");
    expect(runHandoff).not.toHaveBeenCalled();
    vi.mocked(runHandoff).mockRejectedValue(new Error("saved at /tmp/retry.json"));
    expect(await tools.get("mem0_handoff")!.execute({}, exec)).toContain("saved at /tmp/retry.json");
  });
});
