import { beforeEach, describe, expect, it, vi } from "vitest";

const provider = {
  search: vi.fn(),
  add: vi.fn(),
  getAll: vi.fn(),
};

vi.mock("../providers.ts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../providers.ts")>()),
  createProvider: () => provider,
}));
vi.mock("../telemetry.ts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../telemetry.ts")>()),
  captureEvent: vi.fn(),
}));

const { default: memoryPlugin } = await import("../index.ts");

type Handler = (event: any, ctx?: any) => any;

function register(config: Record<string, unknown> = {}) {
  const handlers = new Map<string, Handler>();
  const api = {
    pluginConfig: { mode: "platform", apiKey: "test-api-key", userId: "alice", ...config },
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
    resolvePath: (p: string) => p,
    registerTool: vi.fn(),
    on: (name: string, handler: Handler) => handlers.set(name, handler),
    registerCli: vi.fn(),
    registerCommand: vi.fn(),
    registerService: vi.fn(),
  };
  memoryPlugin.register(api as any);
  return handlers;
}

const ctx = { sessionKey: "agent:main:main" };

async function turn(handlers: Map<string, Handler>, prompt: string, reply: string) {
  await handlers.get("before_prompt_build")!({ prompt }, ctx);
  await handlers.get("agent_end")!(
    {
      success: true,
      messages: [
        { role: "user", content: "an earlier prompt" },
        { role: "assistant", content: "an earlier reply" },
        { role: "user", content: [{ type: "text", text: prompt }] },
        { role: "assistant", content: [{ type: "toolCall", name: "exec" }] },
        { role: "toolResult", content: "tool output" },
        { role: "assistant", content: [{ type: "text", text: reply }] },
      ],
    },
    ctx,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  provider.search.mockResolvedValue([{ id: "m1", memory: "Alice prefers tea" }]);
  provider.add.mockResolvedValue({ results: [] });
});

describe("automatic recall", () => {
  it("searches once, on the first prompt, and injects that context only once", async () => {
    const handlers = register();

    const first = await handlers.get("before_prompt_build")!({ prompt: "What should I drink this morning?" }, ctx);
    const second = await handlers.get("before_prompt_build")!({ prompt: "And what about the evening?" }, ctx);

    expect(provider.search).toHaveBeenCalledTimes(1);
    expect(provider.search).toHaveBeenCalledWith("What should I drink this morning?", {
      user_id: "alice",
      top_k: 5,
      threshold: undefined,
      rerank: false,
      latest_only: true,
      source: "OPENCLAW",
    });
    expect(first.prependContext).toContain("1. Alice prefers tea");
    expect(second).toBeUndefined();
  });

  it("skips recall when the first prompt is shorter than 20 characters", async () => {
    const handlers = register();

    await handlers.get("before_prompt_build")!({ prompt: "hi there" }, ctx);
    await handlers.get("before_prompt_build")!({ prompt: "What should I drink this morning?" }, ctx);

    expect(provider.search).not.toHaveBeenCalled();
  });

  it("recalls again after the session ends", async () => {
    const handlers = register({ autoCapture: false });

    await handlers.get("before_prompt_build")!({ prompt: "What should I drink this morning?" }, ctx);
    await handlers.get("session_end")!({ reason: "daily" }, ctx);
    await handlers.get("before_prompt_build")!({ prompt: "What should I drink this morning?" }, ctx);

    expect(provider.search).toHaveBeenCalledTimes(2);
  });
});

describe("automatic capture", () => {
  it("sends the prompt and final reply at five exchanges, then the rest at session end", async () => {
    const handlers = register({ autoRecall: false });

    for (let n = 0; n < 4; n++) await turn(handlers, `question ${n}`, `answer ${n}`);
    expect(provider.add).not.toHaveBeenCalled();

    await turn(handlers, "question 4", "answer 4");
    await turn(handlers, "question 5", "answer 5");
    await vi.waitFor(() => expect(provider.add).toHaveBeenCalledTimes(1));
    const [batch, options] = provider.add.mock.calls[0];
    expect(batch).toHaveLength(10);
    expect(batch.slice(0, 2)).toEqual([
      { role: "user", content: "question 0" },
      { role: "assistant", content: "answer 0" },
    ]);
    expect(options).toMatchObject({ user_id: "alice", source: "OPENCLAW" });
    expect(options).not.toHaveProperty("run_id");

    await handlers.get("session_end")!({ reason: "new" }, ctx);
    expect(provider.add).toHaveBeenCalledTimes(2);
    expect(provider.add.mock.calls[1][0]).toEqual([
      { role: "user", content: "question 5" },
      { role: "assistant", content: "answer 5" },
    ]);
  });

  it("flushes pending messages before compaction", async () => {
    const handlers = register({ autoRecall: false });

    await turn(handlers, "question 0", "answer 0");
    await handlers.get("before_compaction")!({}, ctx);

    expect(provider.add).toHaveBeenCalledTimes(1);
    expect(provider.add.mock.calls[0][0]).toEqual([
      { role: "user", content: "question 0" },
      { role: "assistant", content: "answer 0" },
    ]);
  });

  it("ignores subagent and cron sessions", async () => {
    const handlers = register();
    const subagent = { sessionKey: "agent:main:subagent:1234" };

    await handlers.get("before_prompt_build")!({ prompt: "question from a subagent" }, subagent);
    await handlers.get("agent_end")!({ success: true, messages: [{ role: "assistant", content: "done" }] }, subagent);
    await handlers.get("agent_end")!({ success: true, messages: [] }, { ...ctx, trigger: "cron" });
    await handlers.get("session_end")!({}, subagent);

    expect(provider.add).not.toHaveBeenCalled();
  });
});
