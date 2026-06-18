import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";

// Capture every mem0ai SDK call so we can assert the tool -> SDK -> scope wiring
// without a live Mem0 platform or a real API key.
const calls: Array<[string, ...unknown[]]> = [];

class FakeMemoryClient {
  client = { get: async (path: string) => ({ data: { path } }) };
  constructor(public opts: unknown) {}
  async add(messages: unknown, params: unknown) {
    calls.push(["add", messages, params]);
    return { id: "mem_1" };
  }
  async search(query: unknown, params: unknown) {
    calls.push(["search", query, params]);
    return { results: [] };
  }
  async getAll(params: unknown) {
    calls.push(["getAll", params]);
    return { results: [], count: 0 };
  }
  async getProject() {
    return { customCategories: [] };
  }
  async updateProject(params: unknown) {
    calls.push(["updateProject", params]);
    return {};
  }
}

mock.module("mem0ai", () => ({ MemoryClient: FakeMemoryClient }));

// Import AFTER the mock so the plugin constructs the fake client.
const { default: Mem0Plugin } = await import("./kilo-mem0");

function ctx() {
  return {
    $: () => ({ quiet: async () => ({ stdout: "" }) }),
    client: { app: { log: async () => {} } },
  } as any;
}

describe("kilo-mem0 tool execution (mocked mem0ai SDK)", () => {
  beforeEach(() => {
    calls.length = 0;
    process.env.MEM0_API_KEY = "m0-testkey1234567890";
    process.env.MEM0_TELEMETRY = "false"; // no PostHog fetch during tests
  });

  afterEach(() => {
    delete process.env.MEM0_API_KEY;
    delete process.env.MEM0_TELEMETRY;
  });

  test("search_memories calls the SDK with scoped filters and returns JSON", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.search_memories.execute({ query: "auth bug", scope: "project" }, {} as any);

    const call = calls.find((c) => c[0] === "search");
    expect(call).toBeDefined();
    expect(call![1]).toBe("auth bug");
    expect((call![2] as any).filters).toBeDefined();
    expect(() => JSON.parse(res)).not.toThrow();
  });

  test("add_memory stamps source=kilo metadata and calls the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.add_memory.execute({ text: "use bun for tests" }, {} as any);

    const call = calls.find((c) => c[0] === "add");
    expect(call).toBeDefined();
    expect((call![2] as any).metadata.source).toBe("kilo");
    expect(() => JSON.parse(res)).not.toThrow();
  });

  test("get_event_status uses the SDK's authed raw client", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.get_event_status.execute({ event_id: "evt_42" }, {} as any);

    expect(JSON.parse(res)).toEqual({ path: "/v1/event/evt_42/" });
  });
});
