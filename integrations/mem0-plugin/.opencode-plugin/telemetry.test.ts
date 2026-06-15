import { afterEach, describe, expect, test } from "bun:test";
import { buildEvent, captureEvent, isTelemetryEnabled } from "./telemetry";

const KEY = "m0-testkey123";

afterEach(() => {
  delete process.env.MEM0_TELEMETRY;
});

describe("opencode telemetry", () => {
  test("buildEvent uses the shared plugin.* schema with platform=opencode", () => {
    const payload = buildEvent("session_start", { memory_count: 5 }, KEY);
    expect(payload).not.toBeNull();
    const props = payload!.properties as Record<string, unknown>;
    expect(payload!.event).toBe("plugin.session_start");
    expect(props.source).toBe("plugin");
    expect(props.platform).toBe("opencode");
    expect(props.memory_count).toBe(5);
    expect(props.$process_person_profile).toBe(false);
    expect(typeof props.plugin_version).toBe("string");
  });

  test("distinct_id is sha256(apiKey)[:32] — matches the editor plugin", async () => {
    const { createHash } = await import("node:crypto");
    const expected = createHash("sha256").update(KEY).digest("hex").slice(0, 32);
    expect(buildEvent("session_start", {}, KEY)!.distinct_id).toBe(expected);
  });

  test("system properties win over caller-supplied ones", () => {
    const props = buildEvent("x", { platform: "HACK", source: "HACK" }, KEY)!
      .properties as Record<string, unknown>;
    expect(props.platform).toBe("opencode");
    expect(props.source).toBe("plugin");
  });

  test("returns null without an API key (no anonymous events)", () => {
    expect(buildEvent("session_start", {}, undefined)).toBeNull();
  });

  test("opt-out via MEM0_TELEMETRY disables events", () => {
    process.env.MEM0_TELEMETRY = "false";
    expect(isTelemetryEnabled()).toBe(false);
    expect(buildEvent("session_start", {}, KEY)).toBeNull();
  });

  test("captureEvent never throws (and sends nothing when opted out)", () => {
    process.env.MEM0_TELEMETRY = "false";
    expect(() => captureEvent("session_start", {}, KEY)).not.toThrow();
    expect(() => captureEvent("session_start", {}, undefined)).not.toThrow();
  });
});
