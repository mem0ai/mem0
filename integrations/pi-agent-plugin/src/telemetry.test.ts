import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  _getEventQueue,
  _resetForTesting,
  captureCommandEvent,
  captureEvent,
  captureToolEvent,
} from "./telemetry.ts";

const CTX = { apiKey: "m0-testkey123" };

function findEvent(name: string): Record<string, unknown> | undefined {
  return _getEventQueue().find((e) => (e as Record<string, unknown>).event === name) as
    | Record<string, unknown>
    | undefined;
}

beforeEach(() => {
  delete process.env.MEM0_TELEMETRY;
  _resetForTesting();
});

afterEach(() => {
  delete process.env.MEM0_TELEMETRY;
  _resetForTesting();
});

describe("pi-agent telemetry", () => {
  it.each(["add", "search", "update", "delete"])(
    "captureToolEvent tracks the %s operation as pi.tool.mem0_memory",
    (action) => {
      captureToolEvent(action, { success: true }, CTX);
      const ev = findEvent("pi.tool.mem0_memory");
      expect(ev).toBeDefined();
      const props = ev!.properties as Record<string, unknown>;
      expect(props.action).toBe(action);
      expect(props.success).toBe(true);
      expect(props.source).toBe("PI_AGENT_PLUGIN");
      expect(props.$process_person_profile).toBe(false);
    },
  );

  it("captureCommandEvent emits a namespaced pi.command.* event", () => {
    captureCommandEvent("mem0-search", { result_count: 3 }, CTX);
    const ev = findEvent("pi.command.mem0-search");
    expect(ev).toBeDefined();
    expect((ev!.properties as Record<string, unknown>).result_count).toBe(3);
  });

  it("respects the MEM0_TELEMETRY opt-out", () => {
    process.env.MEM0_TELEMETRY = "false";
    captureEvent("pi.session.start", {}, CTX);
    captureToolEvent("add", {}, CTX);
    expect(_getEventQueue()).toHaveLength(0);
  });
});
