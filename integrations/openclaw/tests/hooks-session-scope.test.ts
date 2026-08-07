import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockSdk = vi.hoisted(() => ({
  addOptions: [] as Record<string, unknown>[],
  searchOptions: [] as Record<string, unknown>[],
}));

const mockOss = vi.hoisted(() => ({
  addOptions: [] as Record<string, unknown>[],
  searchOptions: [] as Record<string, unknown>[],
}));

vi.mock("mem0ai", () => ({
  default: class MockMemoryClient {
    constructor(_options: Record<string, unknown>) {}

    async add(
      _messages: unknown,
      options: Record<string, unknown>,
    ): Promise<{ results: Array<{ id: string; memory: string }> }> {
      mockSdk.addOptions.push(options);
      return { results: [{ id: "memory-1", memory: "stored" }] };
    }

    async search(
      _query: string,
      options: Record<string, unknown>,
    ): Promise<Array<{ id: string; memory: string; score: number }>> {
      mockSdk.searchOptions.push(options);
      return [{ id: "memory-1", memory: "found", score: 0.9 }];
    }

    async getAll(): Promise<[]> {
      return [];
    }

    async get(): Promise<Record<string, never>> {
      return {};
    }

    async update(): Promise<void> {}

    async delete(): Promise<void> {}

    async deleteAll(): Promise<void> {}
  },
}));

import memoryPlugin from "../index.ts";

type Handler = (...args: any[]) => unknown;

function createPluginApi(config: Record<string, unknown> = {}) {
  const handlers = new Map<string, Handler[]>();
  const tools: any[] = [];
  const api = {
    pluginConfig: {
      mode: "platform",
      apiKey: "test-api-key",
      userId: "alice",
      autoRecall: false,
      autoCapture: true,
      ...config,
    },
    logger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
    },
    resolvePath: vi.fn((path: string) => path),
    registerTool: vi.fn((tool: unknown) => tools.push(tool)),
    on: vi.fn((event: string, handler: Handler) => {
      const eventHandlers = handlers.get(event) ?? [];
      eventHandlers.push(handler);
      handlers.set(event, eventHandlers);
    }),
    registerCli: vi.fn(),
    registerCommand: vi.fn(),
    registerService: vi.fn(),
    registerMemoryCapability: vi.fn(),
  };

  memoryPlugin.register(api as any);
  return { api, handlers, tools };
}

const captureEvent = {
  success: true,
  messages: [
    {
      role: "user",
      content:
        "Remember that the deployment uses the staging database for validation and must be promoted after the migration completes.",
    },
    {
      role: "assistant",
      content:
        "The deployment plan is recorded with the staging database validation step.",
    },
  ],
};

beforeEach(() => {
  mockSdk.addOptions.length = 0;
  mockSdk.searchOptions.length = 0;
  mockOss.addOptions.length = 0;
  mockOss.searchOptions.length = 0;
});

afterEach(() => {
  vi.doUnmock("mem0ai/oss");
});

describe("OpenClaw session scope reaches the SDK payload", () => {
  it("passes the session ID as runId for auto-capture", async () => {
    const { handlers } = createPluginApi();
    await handlers.get("agent_end")?.[0](captureEvent, {
      sessionKey: "sess-abc",
    });

    await vi.waitFor(() => expect(mockSdk.addOptions).toHaveLength(1));
    expect(mockSdk.addOptions[0]).toMatchObject({
      userId: "alice",
      runId: "sess-abc",
      source: "OPENCLAW",
    });
  });

  it("passes the session ID as runId for session and all searches", async () => {
    const { api, handlers, tools } = createPluginApi({
      autoCapture: false,
      autoRecall: true,
    });
    await handlers.get("before_prompt_build")?.[0](
      { prompt: "a".repeat(100) },
      { sessionKey: "sess-abc" },
    );
    mockSdk.searchOptions.length = 0;
    const searchTool = tools.find((tool) => tool.name === "memory_search");

    await searchTool.execute("call-session", {
      query: "session facts",
      scope: "session",
    });
    await searchTool.execute("call-all", {
      query: "all facts",
      scope: "all",
    });

    expect(mockSdk.searchOptions).toHaveLength(3);
    expect(mockSdk.searchOptions[0].filters).toEqual({
      user_id: "alice",
      run_id: "sess-abc",
    });
    expect(mockSdk.searchOptions[1].filters).toEqual({ user_id: "alice" });
    expect(mockSdk.searchOptions[2].filters).toEqual({
      user_id: "alice",
      run_id: "sess-abc",
    });
  });

  it("keeps long-term and cold-start recall unscoped", async () => {
    const { handlers } = createPluginApi({ autoRecall: true });
    await handlers.get("before_prompt_build")?.[0](
      { prompt: "short prompt" },
      { sessionKey: "sess-abc" },
    );

    expect(mockSdk.searchOptions).toHaveLength(2);
    for (const options of mockSdk.searchOptions) {
      expect(options.filters).toEqual({ user_id: "alice" });
    }
  });

  it("keeps sessionless capture without runId", async () => {
    const { handlers } = createPluginApi();
    await handlers.get("agent_end")?.[0](captureEvent, {});

    await vi.waitFor(() => expect(mockSdk.addOptions).toHaveLength(1));
    expect(mockSdk.addOptions[0]).toMatchObject({
      userId: "alice",
      source: "OPENCLAW",
    });
    expect(mockSdk.addOptions[0]).not.toHaveProperty("runId");
  });

  it("preserves non-interactive and subagent capture skips", async () => {
    const positiveControl = createPluginApi();
    await positiveControl.handlers.get("agent_end")?.[0](captureEvent, {
      sessionKey: "sess-positive-control",
    });
    await vi.waitFor(() => expect(mockSdk.addOptions).toHaveLength(1));
    mockSdk.addOptions.length = 0;

    const nonInteractive = createPluginApi();
    await nonInteractive.handlers.get("agent_end")?.[0](captureEvent, {
      trigger: "cron",
      sessionKey: "sess-cron",
    });

    const subagent = createPluginApi();
    await subagent.handlers.get("agent_end")?.[0](captureEvent, {
      sessionKey: "agent:main:subagent:uuid-1",
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mockSdk.addOptions).toHaveLength(0);
  });

  it("keeps skills mode on its skills lifecycle path", async () => {
    const { handlers } = createPluginApi({
      autoCapture: true,
      skills: { triage: { enabled: true }, recall: { enabled: false } },
    });

    expect(handlers.get("before_prompt_build")).toHaveLength(1);
    expect(handlers.get("agent_end")).toHaveLength(1);
    await handlers.get("agent_end")?.[0](captureEvent, {
      sessionKey: "sess-skills",
    });

    expect(mockSdk.addOptions).toHaveLength(0);
  });

  it("keeps the agent namespace while applying session scope", async () => {
    const { handlers, tools } = createPluginApi({
      autoCapture: false,
      autoRecall: true,
    });
    await handlers.get("before_prompt_build")?.[0](
      { prompt: "a".repeat(100) },
      { sessionKey: "agent:researcher:uuid-1" },
    );
    mockSdk.searchOptions.length = 0;
    const searchTool = tools.find((tool) => tool.name === "memory_search");

    await searchTool.execute("call-agent", {
      query: "agent facts",
      scope: "session",
      agentId: "researcher",
    });

    expect(mockSdk.searchOptions[0].filters).toEqual({
      user_id: "alice:agent:researcher",
      run_id: "agent:researcher:uuid-1",
    });
  });

  it("passes session run scope through the OSS provider", async () => {
    vi.doMock("mem0ai/oss", () => ({
      PGVector: undefined,
      RedisDB: undefined,
      Qdrant: undefined,
      Memory: class MockOssMemory {
        constructor(_config: Record<string, unknown>) {}

        async getAll(): Promise<[]> {
          return [];
        }

        async add(
          _messages: unknown,
          options: Record<string, unknown>,
        ): Promise<{ results: Array<{ id: string; memory: string }> }> {
          mockOss.addOptions.push(options);
          return { results: [{ id: "memory-oss-1", memory: "stored" }] };
        }

        async search(
          _query: string,
          options: Record<string, unknown>,
        ): Promise<Array<{ id: string; memory: string; score: number }>> {
          mockOss.searchOptions.push(options);
          return [{ id: "memory-oss-1", memory: "found", score: 0.9 }];
        }
      },
    }));

    const { handlers, tools } = createPluginApi({
      mode: "open-source",
      autoCapture: true,
      autoRecall: false,
      oss: { disableHistory: true },
    });
    await handlers.get("agent_end")?.[0](captureEvent, {
      sessionKey: "agent:main:uuid-1",
    });
    await vi.waitFor(() => expect(mockOss.addOptions).toHaveLength(1));
    expect(mockOss.addOptions[0]).toMatchObject({
      userId: "alice",
      runId: "agent:main:uuid-1",
    });
    mockOss.searchOptions.length = 0;

    const searchTool = tools.find((tool) => tool.name === "memory_search");
    await searchTool.execute("call-oss", {
      query: "session facts",
      scope: "session",
    });

    expect(mockOss.searchOptions.at(-1)?.filters).toEqual({
      user_id: "alice",
      run_id: "agent:main:uuid-1",
    });
  });
});
