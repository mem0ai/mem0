import { beforeEach, describe, expect, it, vi } from "vitest";

const { provider, createProvider } = vi.hoisted(() => {
  const provider = {
    add: vi.fn(),
    search: vi.fn(),
    get: vi.fn(),
    getAll: vi.fn(),
    delete: vi.fn(),
  };

  return {
    provider,
    createProvider: vi.fn(() => provider),
  };
});

vi.mock("./providers.ts", () => ({
  createProvider,
}));

import memoryPlugin from "./index.ts";

function createApi() {
  const hooks = new Map<string, Array<(event: unknown, ctx: unknown) => unknown>>();

  return {
    hooks,
    api: {
      pluginConfig: {
        apiKey: "test-key",
        userId: "alice",
        autoRecall: true,
        autoCapture: false,
      },
      logger: {
        info: vi.fn(),
        warn: vi.fn(),
        error: vi.fn(),
        debug: vi.fn(),
      },
      resolvePath: (p: string) => p,
      registerTool: vi.fn(),
      on(
        event: string,
        handler: (event: unknown, ctx: unknown) => unknown,
      ) {
        const handlers = hooks.get(event) ?? [];
        handlers.push(handler);
        hooks.set(event, handlers);
      },
      registerCli: vi.fn(),
      registerService: vi.fn(),
    },
  };
}

describe("auto-recall lifecycle hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    provider.search.mockReset();
  });

  it("registers auto-recall on before_prompt_build instead of before_agent_start", () => {
    const { api, hooks } = createApi();

    memoryPlugin.register(api as any);

    expect(hooks.get("before_prompt_build")).toHaveLength(1);
    expect(hooks.has("before_agent_start")).toBe(false);
  });

  it("still injects recall context from before_prompt_build", async () => {
    const { api, hooks } = createApi();
    provider.search
      .mockResolvedValueOnce([
        {
          id: "mem-1",
          memory: "The user works on OpenClaw plugins.",
          score: 0.92,
        },
      ])
      .mockResolvedValueOnce([]);

    memoryPlugin.register(api as any);

    const hook = hooks.get("before_prompt_build")?.[0];
    expect(hook).toBeDefined();

    const result = await hook!(
      {
        prompt: "Please remind me what repo I have been working on recently?",
        messages: [],
      },
      {},
    );

    expect(provider.search).toHaveBeenNthCalledWith(
      1,
      "Please remind me what repo I have been working on recently?",
      expect.objectContaining({
        user_id: "alice",
      }),
    );
    expect(result).toEqual(
      expect.objectContaining({
        prependContext: expect.stringContaining(
          "The user works on OpenClaw plugins.",
        ),
      }),
    );
  });
});
