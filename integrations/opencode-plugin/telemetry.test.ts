import { createHash } from "node:crypto";

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
    expect(() => captureEvent("session_start", {}, KEY, "proj")).not.toThrow();
  });

  test("every event carries os_version (matches telemetry.py schema)", () => {
    const props = buildEvent("session_start", {}, KEY)!
      .properties as Record<string, unknown>;
    expect(typeof props.os_version).toBe("string");
  });

  test("project_hash is a salted digest of the project id", async () => {
    // Previously asserted the bare sha256(projectId), which is the defect: that
    // digest is reversible by anyone who can guess a project id. Salted with the
    // API key, which is already in play here and is high entropy.
    const { createHash } = await import("node:crypto");
    const expected = createHash("sha256").update(`${KEY}:acme-repo`).digest("hex");
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

describe("project_hash salting", () => {
  const PROJECT = "my-project";

  test("is not a bare digest of the project id", () => {
    // The defect: an unsalted SHA-256 over a guessable identifier is reversible
    // by anyone who can enumerate project ids.
    const unsalted = createHash("sha256").update(PROJECT).digest("hex");
    const payload = buildEvent("session_start", {}, KEY, PROJECT) as Record<string, any>;

    expect(payload.properties.project_hash).toBeDefined();
    expect(payload.properties.project_hash).not.toBe(unsalted);
  });

  test("differs per account for the same project", () => {
    const a = buildEvent("session_start", {}, "m0-account-a", PROJECT) as Record<string, any>;
    const b = buildEvent("session_start", {}, "m0-account-b", PROJECT) as Record<string, any>;

    expect(a.properties.project_hash).not.toBe(b.properties.project_hash);
  });

  test("is stable for one account, so joins still work", () => {
    const first = buildEvent("session_start", {}, KEY, PROJECT) as Record<string, any>;
    const second = buildEvent("session_end", {}, KEY, PROJECT) as Record<string, any>;

    expect(first.properties.project_hash).toBe(second.properties.project_hash);
  });

  test("is omitted rather than unsalted when there is no key", () => {
    const payload = buildEvent("session_start", {}, undefined, PROJECT);

    // No key means no event at all, so there is no unsalted hash to leak.
    expect(payload).toBeNull();
  });
});
