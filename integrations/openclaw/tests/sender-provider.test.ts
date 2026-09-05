import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EmbedderFactory, Memory, VectorStoreFactory } from "mem0ai/oss";
import type { VectorStore, VectorStoreResult } from "mem0ai/oss";
import { mem0ConfigSchema } from "../config.ts";
import { createProvider } from "../providers.ts";
import { createSenderScopedProvider } from "../scoped-provider.ts";
import { senderUserId } from "../isolation.ts";
import { createMemorySearchTool } from "../tools/memory-search.ts";
import type { ToolDeps } from "../tools/index.ts";

const aliceId = senderUserId("deployment", {
  agentId: "assistant", channel: "telegram", accountId: "work", senderId: "alice",
});
const bobId = senderUserId("deployment", {
  agentId: "assistant", channel: "telegram", accountId: "work", senderId: "bob",
});
const rows: VectorStoreResult[] = [
  { id: "alice-preference", score: 1, payload: {
    user_id: aliceId, data: "Alice prefers green tea", category: "preference", importance: 0.9,
  } },
  { id: "alice-project", score: 1, payload: {
    user_id: aliceId, data: "Alice is building a compiler", category: "project", importance: 0.5,
  } },
  { id: "bob-private-id", score: 1, payload: {
    user_id: bobId, data: "Bob's private memory", category: "preference", importance: 0.9,
  } },
];

// Only storage is simulated. Memory.search and _processMetadataFilters are the
// actual pinned SDK methods, including its Object.assign-based AND flattening.
function matches(payload: Record<string, unknown>, filters: Record<string, unknown> = {}): boolean {
  return Object.entries(filters).every(([key, condition]) => {
    const actual = payload[key];
    if (condition && typeof condition === "object") {
      return Object.entries(condition).every(([operator, value]) => {
        if (operator === "eq") return actual === value;
        if (operator === "gte") return typeof actual === "number" && typeof value === "number" && actual >= value;
        throw new Error(`Unsupported test storage operator: ${operator}`);
      });
    }
    return actual === condition;
  });
}

const telemetryDescriptors = Object.fromEntries(
  ["_initializeTelemetry", "_captureEvent"].map((name) => {
    const descriptor = Object.getOwnPropertyDescriptor(Memory.prototype, name);
    if (!descriptor) throw new Error(`Missing pinned SDK telemetry method: ${name}`);
    return [name, descriptor];
  }),
);

beforeEach(() => {
  // Avoid telemetry network and user-home writes without replacing SDK search.
  for (const [name, descriptor] of Object.entries(telemetryDescriptors)) {
    Object.defineProperty(Memory.prototype, name, { ...descriptor, value: async () => {} });
  }
  vi.spyOn(console, "warn");
});
afterEach(() => {
  Object.defineProperties(Memory.prototype, telemetryDescriptors);
  vi.restoreAllMocks();
});

function setup(userIdScope: "static" | "per-sender" = "per-sender") {
  const vectorSearch = vi.fn<VectorStore["search"]>(async (_query, topK, filters) =>
    rows.filter((row) => matches(row.payload, filters)).slice(0, topK));
  const storage: VectorStore = {
    search: vectorSearch,
    list: async (filters, topK) => {
      const results = rows.filter((row) => matches(row.payload, filters)).slice(0, topK);
      return [results, results.length];
    },
    initialize: async () => {},
    getUserId: async () => "test-only",
    setUserId: async () => {},
    get: async (id) => rows.find((row) => row.id === id) ?? null,
    insert: async () => { throw new Error("unexpected write"); },
    update: async () => { throw new Error("unexpected write"); },
    delete: async () => { throw new Error("unexpected write"); },
    deleteCol: async () => { throw new Error("unexpected write"); },
  };
  vi.spyOn(VectorStoreFactory, "create").mockReturnValue(storage);
  vi.spyOn(EmbedderFactory, "create").mockReturnValue({
    embed: async () => [1, 0],
    embedBatch: async (texts) => texts.map(() => [1, 0]),
  });
  const cfg = mem0ConfigSchema.parse({
    mode: "open-source", userId: "deployment", userIdScope,
    oss: {
      disableHistory: true,
      vectorStore: { provider: "memory", config: { dimension: 2 } },
      llm: { provider: "openai", config: { apiKey: "test-only" } },
    },
  });
  const api: ToolDeps["api"] = {
    pluginConfig: {}, resolvePath: (path) => path,
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
    registerTool: vi.fn(), on: vi.fn(), registerCli: vi.fn(), registerService: vi.fn(),
  };
  const rawProvider = createProvider(cfg, api);
  const rawSearch = vi.spyOn(rawProvider, "search");
  const provider = userIdScope === "per-sender"
    ? createSenderScopedProvider(rawProvider, () => aliceId)
    : rawProvider;
  const tool = createMemorySearchTool({
    api, cfg, provider, resolveUserId: () => aliceId,
    effectiveUserId: () => aliceId, agentUserId: () => aliceId,
    buildAddOptions: () => ({ user_id: aliceId }),
    buildSearchOptions: (userId = aliceId, topK = 5, runId) => ({
      user_id: userId, top_k: topK, run_id: runId, threshold: 0,
    }),
    getCurrentSessionId: () => undefined, skillsActive: false, captureToolEvent: vi.fn(),
  });
  return { provider, tool, rawSearch, vectorSearch };
}

const deniedFilters: Array<[string, Record<string, unknown>]> = [
  ["direct user", { user_id: bobId }],
  ["camelCase user", { userId: bobId }],
  ["user equality", { user_id: { eq: bobId } }],
  ["user membership", { user_id: { in: [bobId] } }],
  ["agent", { agent_id: "another-agent" }],
  ["camelCase agent", { agentId: "another-agent" }],
  ["run", { run_id: "another-session" }],
  ["camelCase run", { runId: "another-session" }],
  ["AND", { AND: [{ category: "preference" }, { user_id: bobId }] }],
  ["OR", { OR: [{ user_id: bobId }, { category: "preference" }] }],
  ["NOT", { NOT: [{ user_id: { ne: bobId } }] }],
  ["nested logic", { AND: [{ OR: [{ NOT: [{ userId: bobId }] }] }] }],
  ["nested operator object", { category: { eq: { user_id: bobId } } }],
  ["nested operator array", { category: { in: [{ run_id: "another-session" }] } }],
  ["nested metadata", { metadata: { agent_id: "another-agent" } }],
  ["dotted selector", { "metadata.user_id": bobId }],
  ["own identity override", { user_id: aliceId }],
];

describe("sender isolation through the pinned OSS SDK", () => {
  it("reproduces the unguarded SDK overwrite while leaving static mode unchanged", async () => {
    const { tool, vectorSearch } = setup("static");
    const result = await tool.execute("control", { query: "preferences", filters: { user_id: bobId } });
    expect(vectorSearch).toHaveBeenCalledWith(expect.any(Array), expect.any(Number), { user_id: bobId });
    expect(result.details.memories?.map((memory) => memory.id)).toEqual(["bob-private-id"]);
    expect(result.content[0].text).toContain("Bob's private memory");
  });

  it.each(deniedFilters)("rejects %s before the OSS provider can process filters", async (_name, filters) => {
    const { tool, rawSearch, vectorSearch } = setup();
    const result = await tool.execute("denied", { query: "preferences", filters });
    expect(JSON.stringify(result)).not.toContain("bob-private-id");
    expect(JSON.stringify(result)).not.toContain("Bob's private memory");
    expect(result.details.error).toContain("identity fields are not allowed in advanced filters");
    expect(rawSearch).not.toHaveBeenCalled();
    expect(vectorSearch).not.toHaveBeenCalled();
  });

  it("keeps useful non-identity filters and only returns matching sender memories", async () => {
    const { tool, vectorSearch } = setup();
    const result = await tool.execute("allowed", {
      query: "preferences", filters: { category: { eq: "preference" }, importance: { gte: 0.8 } },
    });
    expect(result.details.memories?.map((memory) => memory.id)).toEqual(["alice-preference"]);
    expect(result.content[0].text).toContain("Alice prefers green tea");
    expect(JSON.stringify(result)).not.toContain("bob-private-id");
    expect(JSON.stringify(result)).not.toContain("Bob's private memory");
    expect(vectorSearch).toHaveBeenCalledWith(expect.any(Array), expect.any(Number), {
      user_id: aliceId, category: { eq: "preference" }, importance: { gte: 0.8 },
    });
  });

  it("guards direct scoped-provider callers, not only model-facing tools", async () => {
    const { provider, rawSearch } = setup();
    await expect(provider.search("preferences", {
      user_id: aliceId, filters: { OR: [{ user_id: bobId }] },
    })).rejects.toThrow("identity fields are not allowed in advanced filters");
    expect(rawSearch).not.toHaveBeenCalled();
  });
});
