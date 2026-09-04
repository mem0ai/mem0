import assert from "node:assert/strict";
import test from "node:test";

import { createTelemetry, errorKind } from "../src/telemetry.ts";

test("telemetry preserves host names and strips sensitive properties", async () => {
  const delivered: Record<string, unknown>[][] = [];
  const telemetry = createTelemetry({
    host: "deepseek",
    source: "DEEPSEEK_HARNESS",
    version: "1.2.3",
    distinctId: "person",
    delivery: async (batch) => {
      delivered.push(batch);
    },
  });

  telemetry.capture("deepseek.tool.search_memory", {
    success: true,
    query: "secret",
    apiKey: "key",
    cwd: "/private/repo",
    repo_id: "raw-repo",
    query_chars: 6,
  });
  await telemetry.flush();
  telemetry.resetForTesting();

  const event = delivered[0][0] as { event: string; properties: Record<string, unknown> };
  assert.equal(event.event, "deepseek.tool.search_memory");
  assert.deepEqual(event.properties, {
    success: true,
    query_chars: 6,
    host: "deepseek",
    source: "DEEPSEEK_HARNESS",
    language: "node",
    plugin_version: "1.2.3",
    node_version: process.version,
    os: process.platform,
    $process_person_profile: false,
    $lib: "posthog-node",
  });
});

test("all false-like opt-out values suppress events", async () => {
  const original = process.env.MEM0_TELEMETRY;
  try {
    for (const value of ["false", "0", "no", "OFF"]) {
      process.env.MEM0_TELEMETRY = value;
      let delivered = false;
      const telemetry = createTelemetry({
        host: "pi",
        source: "PI_AGENT_PLUGIN",
        version: "1",
        distinctId: "person",
        delivery: async () => {
          delivered = true;
        },
      });
      telemetry.capture("pi.test");
      await telemetry.flush();
      telemetry.resetForTesting();
      assert.equal(delivered, false);
    }
  } finally {
    if (original === undefined) delete process.env.MEM0_TELEMETRY;
    else process.env.MEM0_TELEMETRY = original;
  }
});

test("telemetry redacts secrets nested inside allowed properties", () => {
  const secret = "sk-eval-12345678901234567890";
  const telemetry = createTelemetry({
    host: "pi",
    source: "PI_AGENT_PLUGIN",
    version: "1",
    distinctId: "person",
  });

  const event = telemetry.build("pi.test", {
    note: `failure contained ${secret}`,
    details: { authorization: `Bearer ${secret}`, count: 2 },
  });
  telemetry.resetForTesting();

  const serialized = JSON.stringify(event);
  assert.equal(serialized.includes(secret), false);
  assert.equal(serialized.includes("[REDACTED]"), true);
  assert.equal((event?.properties as { details: { count: number } }).details.count, 2);
});

test("telemetry removes sensitive keys from nested list elements", () => {
  const telemetry = createTelemetry({
    host: "pi",
    source: "PI_AGENT_PLUGIN",
    version: "1",
    distinctId: "person",
  });

  const event = telemetry.build("pi.test", {
    details: [
      { password: "plain-password", count: 2 },
      { nested: { token: "plain-token", ok: true } },
    ],
  });
  telemetry.resetForTesting();

  assert.deepEqual((event?.properties as { details: unknown[] }).details, [
    { count: 2 },
    { nested: { ok: true } },
  ]);
});

test("error classification does not expose messages", () => {
  assert.equal(errorKind(new Error("429 secret query")), "rate-limited");
  assert.equal(errorKind(new Error("401 key")), "auth");
  assert.equal(errorKind(new Error("request timeout")), "timeout");
  assert.equal(errorKind(new Error("fetch failed")), "network");
});
