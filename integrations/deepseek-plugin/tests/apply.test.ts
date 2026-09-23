import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

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

  it("registers both memory tools", () => {
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });
    expect([...tools.keys()].sort()).toEqual(["add_memory", "search_memory"]);
  });
});

describe("Harness lifecycle", () => {
  it("recalls memory once, for the first human prompt of the session", async () => {
    mockSearch.mockResolvedValue({
      results: [{ id: "m1", memory: "Likes tea" }],
    });
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const assemble = listeners.get("system-prompt/assemble")!;
    const base = { sections: [], contexts: [], tools: [], variables: {} };

    const messages = [
      { role: "user", content: [{ type: "text", text: "What do I usually drink?" }], source: { kind: "user" } },
    ];
    const context = { agent: { session: { deriveMessages: () => messages } } };

    const result = await assemble(base, context, async () => base);
    messages.push({ role: "user", content: [{ type: "text", text: "And what do I eat?" }], source: { kind: "user" } });
    const second = await assemble(base, context, async () => base);

    expect(mockSearch).toHaveBeenCalledTimes(1);
    expect(mockSearch).toHaveBeenCalledWith("What do I usually drink?", {
      filters: { user_id: "u" },
      topK: 5,
      rerank: false,
      latestOnly: true,
    });
    for (const assembly of [result, second]) {
      expect(assembly).toMatchObject({
        contexts: [{ name: "mem0:recall", text: expect.stringContaining("Likes tea") }],
      });
    }
  });

  it("skips recall for a first prompt shorter than 20 characters", async () => {
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const base = { sections: [], contexts: [], tools: [], variables: {} };
    const deriveMessages = () => [{ role: "user", content: "hi", source: { kind: "user" } }];

    await listeners.get("system-prompt/assemble")!(base, { agent: { session: { deriveMessages } } }, async () => base);

    expect(mockSearch).not.toHaveBeenCalled();
  });

  it("captures at the five-exchange checkpoint and flushes the rest when the session is disposed", async () => {
    mockAdd.mockResolvedValue({ eventId: "evt-1", status: "PENDING" });
    const listeners = applyAndCollectListeners({ apiKey: "k", userId: "u" });
    const onSessionEvent = listeners.get("session/event")!;
    const session = {};
    const turn = (n: number) => {
      onSessionEvent(session, { type: "turn/start", data: { turn: n } });
      onSessionEvent(session, {
        type: "user/message",
        data: { role: "user", content: [{ type: "text", text: `question ${n}` }], source: { kind: "user" } },
      });
      onSessionEvent(session, {
        type: "assistant/message",
        data: { turn: n, message: { role: "assistant", content: [{ type: "text", text: `answer ${n}` }] } },
      });
      onSessionEvent(session, { type: "turn/end", data: { turn: n, reason: { kind: "completed" } } });
    };

    for (let n = 0; n < 4; n++) turn(n);
    await Promise.resolve();
    expect(mockAdd).not.toHaveBeenCalled();

    turn(4);
    turn(5);
    await vi.waitFor(() => expect(mockAdd).toHaveBeenCalledTimes(1));
    const [batch, options] = mockAdd.mock.calls[0];
    expect(batch).toHaveLength(10);
    expect(batch.at(-1)).toEqual({ role: "assistant", content: "answer 4" });
    expect(options).toEqual({ userId: "u", source: "DEEPSEEK_HARNESS" });

    listeners.get("session/disposed")!(session);
    await vi.waitFor(() => expect(mockAdd).toHaveBeenCalledTimes(2));
    expect(mockAdd.mock.calls[1][0]).toEqual([
      { role: "user", content: "question 5" },
      { role: "assistant", content: "answer 5" },
    ]);
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
    expect(listeners.has("session/disposed")).toBe(false);
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
