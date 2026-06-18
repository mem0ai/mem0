import { afterEach, describe, expect, test } from "bun:test";
import { buildEvent, captureEvent, isTelemetryEnabled } from "./telemetry";

const KEY = "m0-testkey123";

afterEach(() => {
  delete process.env.MEM0_TELEMETRY;
});

describe("kilo telemetry", () => {
  test("buildEvent uses the shared plugin.* schema with platform=kilo", () => {
    const payload = buildEvent("session_start", { memory_count: 5 }, KEY);
    expect(payload).not.toBeNull();
    const props = payload!.properties as Record<string, unknown>;
    expect(payload!.event).toBe("plugin.session_start");
    expect(props.source).toBe("plugin");
    expect(props.platform).toBe("kilo");
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
    expect(props.platform).toBe("kilo");
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
    expect(() => captureEvent("session_start", {}, KEY, "proj")).not.toThrow();
  });

  test("every event carries os_version (matches telemetry.py schema)", () => {
    const props = buildEvent("session_start", {}, KEY)!
      .properties as Record<string, unknown>;
    expect(typeof props.os_version).toBe("string");
  });

  test("project_hash is sha256(projectId) when a project id is supplied", async () => {
    const { createHash } = await import("node:crypto");
    const expected = createHash("sha256").update("acme-repo").digest("hex");
    const props = buildEvent("session_start", {}, KEY, "acme-repo")!
      .properties as Record<string, unknown>;
    expect(props.project_hash).toBe(expected);
  });

  test("project_hash is omitted when no project id is supplied (no raw ids leak)", () => {
    const props = buildEvent("session_start", {}, KEY)!
      .properties as Record<string, unknown>;
    expect("project_hash" in props).toBe(false);
  });

  test("expanded event types all use the shared plugin.* namespace", () => {
    for (const ev of ["user_prompt", "bash_error", "pre_compact", "session_stop"]) {
      expect(buildEvent(ev, {}, KEY)!.event).toBe(`plugin.${ev}`);
    }
  });
});
