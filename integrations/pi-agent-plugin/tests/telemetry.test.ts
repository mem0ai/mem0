import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("node:fs", () => ({
  existsSync: vi.fn().mockReturnValue(false),
  readFileSync: vi.fn().mockReturnValue("{}"),
  writeFileSync: vi.fn(),
  mkdirSync: vi.fn(),
  unlinkSync: vi.fn(),
}));

import {
  captureEvent,
  captureToolEvent,
  captureCommandEvent,
  _getEventQueue,
  _resetForTesting,
} from "../src/telemetry.ts";

describe("telemetry", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    delete process.env.MEM0_TELEMETRY;
    _resetForTesting();
    fetchSpy = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.MEM0_TELEMETRY;
  });

  it("queues an event with correct name and standard properties", () => {
    captureEvent("pi.test.event", { custom: 42 });
    const queue = _getEventQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].event).toBe("pi.test.event");
    const props = queue[0].properties as Record<string, unknown>;
    expect(props.source).toBe("PI_AGENT_PLUGIN");
    expect(props.language).toBe("node");
    expect(props.custom).toBe(42);
    expect(props.$process_person_profile).toBe(false);
  });

  it("uses SHA-256 of apiKey as distinct_id when provided", () => {
    captureEvent("test", {}, { apiKey: "m0-testkey" });
    const queue = _getEventQueue();
    expect(queue[0].distinct_id).toMatch(/^[a-f0-9]{64}$/);
    expect(queue[0].distinct_id).not.toBe("m0-testkey");
  });

  it("generates a persistent anonymous id when no apiKey", () => {
    captureEvent("test", {}, {});
    const queue = _getEventQueue();
    expect(queue[0].distinct_id).toMatch(/^pi-mem0-anon-/);
  });

  it("does not queue events when MEM0_TELEMETRY=false", () => {
    process.env.MEM0_TELEMETRY = "false";
    captureEvent("should.not.appear");
    expect(_getEventQueue()).toHaveLength(0);
  });

  it("does not queue events when MEM0_TELEMETRY=0", () => {
    process.env.MEM0_TELEMETRY = "0";
    captureEvent("should.not.appear");
    expect(_getEventQueue()).toHaveLength(0);
  });

  it("does not queue events when MEM0_TELEMETRY=off", () => {
    process.env.MEM0_TELEMETRY = "off";
    captureEvent("should.not.appear");
    expect(_getEventQueue()).toHaveLength(0);
  });

  it("re-enables telemetry when env var is cleared between calls", () => {
    process.env.MEM0_TELEMETRY = "false";
    captureEvent("blocked");
    expect(_getEventQueue()).toHaveLength(0);

    delete process.env.MEM0_TELEMETRY;
    captureEvent("allowed");
    expect(_getEventQueue()).toHaveLength(1);
    expect(_getEventQueue()[0].event).toBe("allowed");
  });

  it("flushes via fetch when queue reaches threshold", () => {
    for (let i = 0; i < 10; i++) {
      captureEvent(`event_${i}`);
    }
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(_getEventQueue()).toHaveLength(0);
  });

  it("captureToolEvent uses pi.tool.mem0_memory event name with action property", () => {
    captureToolEvent("search", { success: true, latency_ms: 42 });
    const queue = _getEventQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].event).toBe("pi.tool.mem0_memory");
    const props = queue[0].properties as Record<string, unknown>;
    expect(props.action).toBe("search");
    expect(props.success).toBe(true);
    expect(props.latency_ms).toBe(42);
  });

  it("captureCommandEvent uses pi.command.<name> event name", () => {
    captureCommandEvent("mem0-search", { result_count: 5 });
    const queue = _getEventQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].event).toBe("pi.command.mem0-search");
    const props = queue[0].properties as Record<string, unknown>;
    expect(props.result_count).toBe(5);
  });

  it("never throws even if fetch throws", () => {
    fetchSpy.mockRejectedValueOnce(new Error("network down"));
    expect(() => {
      for (let i = 0; i < 10; i++) captureEvent(`event_${i}`);
    }).not.toThrow();
  });
});
