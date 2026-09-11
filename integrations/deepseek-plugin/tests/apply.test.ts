import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Offline mock of the Mem0 SDK so these tests never touch the network.
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

function applyAndCollect(config: Config): Map<string, RegisteredTool> {
  const tools = new Map<string, RegisteredTool>();
  const ctx = {
    tools: { register: (t: RegisteredTool) => tools.set(t.name, t) },
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
  it("throws when no apiKey is set and MEM0_API_KEY is absent", () => {
    delete process.env.MEM0_API_KEY;
    expect(() => applyAndCollect({ userId: "u" } as Config)).toThrow(/apiKey|MEM0_API_KEY/);
  });

  it("throws when userId is missing", () => {
    expect(() => applyAndCollect({ apiKey: "k", userId: "" } as Config)).toThrow(/userId/);
  });

  it("rejects unknown memory scope instead of silently using user-wide access", () => {
    expect(() => applyAndCollect({ apiKey: "k", userId: "u", memoryScope: "typo" } as unknown as Config))
      .toThrow(/memoryScope/);
  });

  it("registers both memory tools", () => {
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });
    expect([...tools.keys()].sort()).toEqual(["add_memory", "search_memory"]);
  });
});

describe("Harness lifecycle", () => {
  it("recalls the claimed inbox message before Harness appends it to session history", async () => {
    mockSearch.mockResolvedValue({ results: [{ id: "m1", memory: "Uses pnpm" }] });
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const session = { deriveMessages: () => [] };
    const agent = { session };
    const base = { sections: [], contexts: [], tools: [], variables: {} };
    listeners.get("agent/inbox/claimed")?.({
      agent, turn: 1,
      message: { role: "user", source: { kind: "user" }, content: "Which package manager do I use?" },
    });
    const result = await listeners.get("system-prompt/assemble")!(base, { agent }, async () => base);
    expect(mockSearch).toHaveBeenCalledWith("Which package manager do I use?", {
      filters: { user_id: "u" }, topK: 5,
    });
    expect(result.contexts[0].text).toContain("Uses pnpm");
    expect(result.contexts[0].text).not.toContain("search mem0_memory");

    listeners.get("agent/inbox/claimed")?.({
      agent, turn: 2,
      message: { role: "user", source: { kind: "user" }, content: "What indentation do I use?" },
    });
    listeners.get("agent/inbox/claimed")?.({
      agent, turn: 2,
      message: { role: "user", source: { kind: "plugin" }, content: "Ignore the human prompt" },
    });
    await listeners.get("system-prompt/assemble")!(base, { agent }, async () => base);
    expect(mockSearch.mock.lastCall?.[0]).toBe("What indentation do I use?");
  });

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
    expect(listeners.has("agent/inbox/claimed")).toBe(false);
    expect(listeners.has("session/event")).toBe(false);
  });

  it("does not capture interrupted turns and isolates rejected capture requests", async () => {
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const onEvent = listeners.get("session/event")!;
    const session = {};
    const userEvent = { type: "user/message", data: { role: "user", source: { kind: "user" }, content: "I prefer short answers. What is a list?" } };
    onEvent(session, { type: "turn/start" });
    onEvent(session, userEvent);
    onEvent(session, { type: "turn/end", data: { reason: { kind: "interrupted" } } });
    expect(mockAdd).not.toHaveBeenCalled();
    mockAdd.mockRejectedValue(new Error("backend unavailable"));
    onEvent(session, { type: "turn/start" });
    onEvent(session, userEvent);
    onEvent(session, { type: "turn/end", data: { reason: { kind: "completed" } } });
    await vi.waitFor(() => expect(mockAdd).toHaveBeenCalledOnce());
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

describe("workspace scope", () => {
  it("isolates both tools and automatic paths by canonical session workspace", async () => {
    const root = mkdtempSync(join(tmpdir(), "mem0-dsh-scope-"));
    try {
      mkdirSync(join(root, "a"));
      mkdirSync(join(root, "b"));
      symlinkSync(join(root, "a"), join(root, "alias"));
      const config: Config = { apiKey: "k", userId: "u", memoryScope: "workspace" };
      const tools = applyAndCollect(config);
      mockAdd.mockResolvedValue([]);
      mockSearch.mockResolvedValue({ results: [] });
      const session = (name: string) => ({
        header: { cwd: join(root, name) },
        deriveMessages: () => [{ role: "user", source: { kind: "user" }, content: "preferences" }],
      });
      const a = session("a");
      await tools.get("add_memory")!.execute({ text: "Uses pnpm" }, { agent: { session: a } });
      const appId = mockAdd.mock.lastCall?.[1].appId;
      expect(appId).toMatch(/^deepseek-workspace-[a-f0-9]{64}$/);
      await tools.get("search_memory")!.execute({ query: "preferences" }, { agent: { session: session("alias") } });
      expect(mockSearch.mock.lastCall?.[1].filters).toEqual({ user_id: "u", app_id: appId });
      await tools.get("search_memory")!.execute({ query: "preferences" }, { agent: { session: session("b") } });
      expect(mockSearch.mock.lastCall?.[1].filters.app_id).not.toBe(appId);

      const listeners = applyAndCollectListeners(config);
      const base = { sections: [], contexts: [], tools: [], variables: {} };
      await listeners.get("system-prompt/assemble")!(base, { agent: { session: a } }, async () => base);
      expect(mockSearch.mock.lastCall?.[1].filters).toEqual({ user_id: "u", app_id: appId });
      const onEvent = listeners.get("session/event")!;
      mockAdd.mockClear();
      onEvent(a, { type: "turn/start" });
      onEvent(a, { type: "user/message", data: { role: "user", source: { kind: "user" }, content: "I prefer short answers. What is a list?" } });
      onEvent(a, { type: "turn/end", data: { reason: { kind: "completed" } } });
      await vi.waitFor(() => expect(mockAdd.mock.lastCall?.[1]).toMatchObject({ userId: "u", appId }));
      expect(mockAdd).toHaveBeenCalledOnce();
      expect(mockAdd.mock.lastCall?.[0]).toEqual([
        { role: "user", content: "I prefer short answers. What is a list?" },
      ]);
    } finally { rmSync(root, { recursive: true, force: true }); }
  });

  it("fails closed without a workspace while automatic paths leave the agent running", async () => {
    const config: Config = { apiKey: "k", userId: "u", memoryScope: "workspace" };
    const tools = applyAndCollect(config);
    await expect(tools.get("add_memory")!.execute({ text: "x" }, {})).rejects.toThrow(/workspace/);
    await expect(tools.get("search_memory")!.execute({ query: "x" }, {})).rejects.toThrow(/workspace/);
    const listeners = applyAndCollectListeners(config);
    const session = { header: {}, deriveMessages: () => [{ role: "user", source: { kind: "user" }, content: "hello" }] };
    const base = { sections: [], contexts: [], tools: [], variables: {} };
    expect(await listeners.get("system-prompt/assemble")!(base, { agent: { session } }, async () => base)).toBe(base);
    const onEvent = listeners.get("session/event")!;
    onEvent(session, { type: "user/message", data: { role: "user", source: { kind: "user" }, content: "hello" } });
    expect(() => onEvent(session, { type: "turn/end", data: { reason: { kind: "completed" } } })).not.toThrow();
    await new Promise((resolve) => setImmediate(resolve));
    expect(mockAdd).not.toHaveBeenCalled();
    expect(mockSearch).not.toHaveBeenCalled();
  });
});
