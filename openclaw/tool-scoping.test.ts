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
  const tools = new Map<string, unknown>();

  return {
    tools,
    api: {
      pluginConfig: {
        apiKey: "test-key",
        userId: "alice",
        autoRecall: false,
        autoCapture: false,
      },
      logger: {
        info: vi.fn(),
        warn: vi.fn(),
        error: vi.fn(),
        debug: vi.fn(),
      },
      resolvePath: (p: string) => p,
      registerTool(definition: unknown, metadata?: Record<string, unknown>) {
        const name = (metadata?.name as string | undefined)
          ?? (typeof definition === "object" && definition && "name" in (definition as Record<string, unknown>)
            ? ((definition as Record<string, unknown>).name as string | undefined)
            : undefined);

        if (!name) {
          throw new Error("tool registration missing name");
        }

        tools.set(name, definition);
      },
      on: vi.fn(),
      registerCli: vi.fn(),
      registerService: vi.fn(),
    },
  };
}

function createTool(
  tools: Map<string, unknown>,
  name: string,
  ctx: { sessionKey?: string },
) {
  const registration = tools.get(name);
  if (!registration) throw new Error(`missing tool registration for ${name}`);
  return typeof registration === "function"
    ? registration(ctx)
    : registration;
}

describe("tool session scoping", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    provider.search.mockResolvedValue([]);
    provider.add.mockResolvedValue({ results: [] });
    provider.get.mockResolvedValue({
      id: "mem-1",
      memory: "stored memory",
    });
    provider.getAll.mockResolvedValue([]);
    provider.delete.mockResolvedValue(undefined);
  });

  it("scopes memory_search to the tool factory session context", async () => {
    const { api, tools } = createApi();
    memoryPlugin.register(api as any);

    const betaSearch = createTool(tools, "memory_search", {
      sessionKey: "agent:beta:session-b",
    }) as { execute: (toolCallId: string, params: Record<string, unknown>) => Promise<unknown> };
    const alphaSearch = createTool(tools, "memory_search", {
      sessionKey: "agent:alpha:session-a",
    }) as { execute: (toolCallId: string, params: Record<string, unknown>) => Promise<unknown> };

    await betaSearch.execute("tool-beta", { query: "project", scope: "session" });
    await alphaSearch.execute("tool-alpha", { query: "project", scope: "session" });

    expect(provider.search).toHaveBeenNthCalledWith(
      1,
      "project",
      expect.objectContaining({
        user_id: "alice:agent:beta",
        run_id: "agent:beta:session-b",
      }),
    );
    expect(provider.search).toHaveBeenNthCalledWith(
      2,
      "project",
      expect.objectContaining({
        user_id: "alice:agent:alpha",
        run_id: "agent:alpha:session-a",
      }),
    );
  });

  it("scopes session memory writes to the tool factory session context", async () => {
    const { api, tools } = createApi();
    memoryPlugin.register(api as any);

    const betaStore = createTool(tools, "memory_store", {
      sessionKey: "agent:beta:session-b",
    }) as { execute: (toolCallId: string, params: Record<string, unknown>) => Promise<unknown> };
    const alphaStore = createTool(tools, "memory_store", {
      sessionKey: "agent:alpha:session-a",
    }) as { execute: (toolCallId: string, params: Record<string, unknown>) => Promise<unknown> };

    await betaStore.execute("tool-beta", { text: "beta fact", longTerm: false });
    await alphaStore.execute("tool-alpha", { text: "alpha fact", longTerm: false });

    expect(provider.add).toHaveBeenNthCalledWith(
      1,
      [{ role: "user", content: "beta fact" }],
      expect.objectContaining({
        user_id: "alice:agent:beta",
        run_id: "agent:beta:session-b",
      }),
    );
    expect(provider.add).toHaveBeenNthCalledWith(
      2,
      [{ role: "user", content: "alpha fact" }],
      expect.objectContaining({
        user_id: "alice:agent:alpha",
        run_id: "agent:alpha:session-a",
      }),
    );
  });
});
