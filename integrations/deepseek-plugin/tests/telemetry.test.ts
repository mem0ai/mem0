import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const mockSearch = vi.fn();
const mockAdd = vi.fn();
vi.mock("mem0ai", () => ({
  MemoryClient: class {
    telemetryId = "dev@example.com";
    search = mockSearch;
    add = mockAdd;
  },
}));
vi.mock("@deepseek-ai/dsh-tools", () => ({ defineTool: (options: unknown) => options }));

import { apply, type Config } from "../src/index.ts";
import {
  captureEvent,
  errorKind,
  flushEvents,
  isTelemetryEnabled,
  _queueForTesting,
  _resetForTesting,
} from "../src/telemetry.ts";

interface RegisteredTool {
  name: string;
  execute(args: unknown, exec: unknown): Promise<unknown>;
}

function applyAndCollect(config: Config): Map<string, RegisteredTool> {
  const tools = new Map<string, RegisteredTool>();
  apply({ tools: { register: (t: RegisteredTool) => tools.set(t.name, t) } } as never, config);
  return tools;
}

function queued(): Record<string, any>[] {
  return _queueForTesting() as Record<string, any>[];
}

let home: string;
let savedHome: string | undefined;
let savedTelemetry: string | undefined;

beforeEach(() => {
  savedHome = process.env.HOME;
  savedTelemetry = process.env.MEM0_TELEMETRY;
  delete process.env.MEM0_TELEMETRY;
  home = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-deepseek-"));
  process.env.HOME = home;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  mockSearch.mockReset();
  mockAdd.mockReset();
  _resetForTesting();
});

afterEach(() => {
  _resetForTesting();
  vi.unstubAllGlobals();
  fs.rmSync(home, { recursive: true, force: true });
  if (savedHome === undefined) delete process.env.HOME;
  else process.env.HOME = savedHome;
  if (savedTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
  else process.env.MEM0_TELEMETRY = savedTelemetry;
});

describe("opt-out", () => {
  it("queues nothing for every documented off value", () => {
    for (const value of ["false", "0", "no", "OFF"]) {
      process.env.MEM0_TELEMETRY = value;
      expect(isTelemetryEnabled()).toBe(false);
      captureEvent("deepseek.tool.search_memory", {}, { telemetryId: "dev@example.com" });
    }
    expect(queued()).toHaveLength(0);
  });

  it("is on by default", () => {
    expect(isTelemetryEnabled()).toBe(true);
  });
});

describe("identity", () => {
  it("keys events on the account email the SDK resolved", () => {
    captureEvent("deepseek.tool.add_memory", {}, { telemetryId: "dev@example.com" });
    expect(queued()[0].distinct_id).toBe("dev@example.com");
  });

  it("falls back to a persisted anonymous id before the SDK has pinged", () => {
    captureEvent("deepseek.tool.add_memory", {}, {});
    const first = queued()[0].distinct_id as string;
    expect(first).toMatch(/^deepseek-anon-/);

    _resetForTesting();
    captureEvent("deepseek.tool.add_memory", {}, {});
    expect(queued()[0].distinct_id).toBe(first);
  });

  it("aliases the anonymous history onto the email exactly once", () => {
    captureEvent("deepseek.tool.add_memory", {}, {});
    const anonymous = queued()[0].distinct_id;
    _resetForTesting();

    captureEvent("deepseek.tool.add_memory", {}, { telemetryId: "dev@example.com" });
    const [identify, event] = queued();
    expect(identify.event).toBe("$identify");
    expect(identify.distinct_id).toBe("dev@example.com");
    expect(identify.properties.$anon_distinct_id).toBe(anonymous);
    expect(event.distinct_id).toBe("dev@example.com");

    captureEvent("deepseek.tool.add_memory", {}, { telemetryId: "dev@example.com" });
    expect(queued().filter((e) => e.event === "$identify")).toHaveLength(1);
  });
});

describe("event shape", () => {
  it("stamps every event with the integration source and runtime baseline", () => {
    captureEvent("deepseek.tool.search_memory", { success: true }, { telemetryId: "d@e.com" });
    const { properties } = queued()[0];
    expect(properties.source).toBe("DEEPSEEK_HARNESS");
    expect(properties.language).toBe("node");
    expect(properties.$process_person_profile).toBe(false);
    expect(properties.os).toBe(process.platform);
    expect(properties.plugin_version).not.toBe("unknown");
    expect(properties.success).toBe(true);
  });

  it("flushes one batch to PostHog and empties the queue", async () => {
    captureEvent("deepseek.tool.search_memory", {}, { telemetryId: "d@e.com" });
    flushEvents();

    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("posthog.com");
    expect(JSON.parse(init.body).batch).toHaveLength(1);
    expect(queued()).toHaveLength(0);
  });

  it("never throws when the network is gone", () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("fetch failed")));
    captureEvent("deepseek.tool.search_memory", {}, { telemetryId: "d@e.com" });
    expect(() => flushEvents()).not.toThrow();
  });
});

describe("errorKind", () => {
  it("buckets failures without leaking the message", () => {
    expect(errorKind(new Error("Request failed with status 429"))).toBe("rate-limited");
    expect(errorKind(new Error("401 Unauthorized"))).toBe("auth");
    expect(errorKind(new Error("503 Service Unavailable"))).toBe("server-error");
    expect(errorKind(new Error("The operation was aborted due to timeout"))).toBe("timeout");
    expect(errorKind(new Error("fetch failed"))).toBe("network");
    expect(errorKind(new Error("token sk-abcdef is invalid"))).toBe("Error");
  });
});

describe("tool instrumentation", () => {
  it("records a mount, then a successful search with its shape but not its query", async () => {
    mockSearch.mockResolvedValue({ results: [{ id: "m1", memory: "Likes tea" }] });
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    await tools.get("search_memory")!.execute({ query: "what drink", limit: 3 }, {});

    const [mounted, search] = queued();
    expect(mounted.event).toBe("deepseek.plugin.mounted");
    expect(mounted.properties.has_host).toBe(false);
    expect(search.event).toBe("deepseek.tool.search_memory");
    expect(search.properties).toMatchObject({
      success: true,
      top_k: 3,
      result_count: 1,
      query_chars: 10,
      scope_overridden: false,
      has_agent_id: false,
      has_run_id: false,
    });
    expect(typeof search.properties.duration_ms).toBe("number");
    expect(JSON.stringify(search)).not.toContain("what drink");
    expect(JSON.stringify(search)).not.toContain("Likes tea");
  });

  it("records a failed search with a coarse error kind", async () => {
    mockSearch.mockRejectedValue(new Error("429 rate limit exceeded"));
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    await tools.get("search_memory")!.execute({ query: "x" }, {});

    const search = queued().at(-1)!;
    expect(search.properties).toMatchObject({ success: false, error_kind: "rate-limited" });
  });

  it("records a write with its size but not its text", async () => {
    mockAdd.mockResolvedValue([{ id: "m1", memory: "Fact" }]);
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    await tools.get("add_memory")!.execute({ text: "secret fact", userId: "alice" }, {});

    const add = queued().at(-1)!;
    expect(add.event).toBe("deepseek.tool.add_memory");
    expect(add.properties).toMatchObject({
      success: true,
      text_chars: 11,
      memory_count: 1,
      scope_overridden: true,
    });
    expect(JSON.stringify(add)).not.toContain("secret fact");
    expect(JSON.stringify(add)).not.toContain("alice");
  });

  it("records a failed write and still returns the graceful failure line", async () => {
    mockAdd.mockRejectedValue(new Error("boom"));
    const tools = applyAndCollect({ apiKey: "k", userId: "u" });

    const out = await tools.get("add_memory")!.execute({ text: "x" }, {});

    expect(out).toContain("add_memory failed");
    expect(queued().at(-1)!.properties).toMatchObject({ success: false, error_kind: "Error" });
  });
});
