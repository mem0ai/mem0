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

function applyAndCollect(config: Config): Map<string, RegisteredTool> {
  const tools = new Map<string, RegisteredTool>();
  const ctx = {
    tools: { register: (t: RegisteredTool) => tools.set(t.name, t) },
  };
  apply(ctx as never, config);
  return tools;
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
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

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

  it("returns a graceful failure line on error", async () => {
    mockAdd.mockRejectedValue(new Error("boom"));
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("add_memory")!.execute({ text: "x" }, {});

    expect(out).toContain("add_memory failed");
    expect(out).toContain("boom");
  });
});
