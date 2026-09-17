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

for (const key of ["password", "token", "secret", "authorization"]) {
  test(`telemetry removes ${key} from nested list elements`, () => {
    const secret = "sk-eval-12345678901234567890";
    const telemetry = createTelemetry({
      host: "pi",
      source: "PI_AGENT_PLUGIN",
      version: "1",
      distinctId: "person",
    });

    const event = telemetry.build("pi.test", {
      details: [
        { [key]: "plain-value", count: 2 },
        { nested: { [key.toUpperCase()]: "plain-value", ok: true } },
        [`failure contained ${secret}`],
      ],
    });
    telemetry.resetForTesting();

    assert.deepEqual((event?.properties as { details: unknown[] }).details, [
      { count: 2 },
      { nested: { ok: true } },
      ["failure contained [REDACTED]"],
    ]);
  });
}

test("error classification does not expose messages", () => {
  assert.equal(errorKind(new Error("429 secret query")), "rate-limited");
  assert.equal(errorKind(new Error("401 key")), "auth");
  assert.equal(errorKind(new Error("request timeout")), "timeout");
  assert.equal(errorKind(new Error("fetch failed")), "network");
});

test("a failed delivery keeps the batch instead of deleting it", async () => {
  // The defect: the queue was detached before the await and the error swallowed,
  // so one blip destroyed the events with nothing recording that it happened.
  const attempts: Record<string, unknown>[][] = [];
  let failNext = true;
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d",
    flushThreshold: 1000,
    delivery: async (batch) => {
      attempts.push(batch);
      if (failNext) throw new Error("network down");
    },
  });

  telemetry.capture("one");
  telemetry.capture("two");
  await telemetry.flush();

  assert.equal(attempts.length, 1);
  assert.equal(telemetry.queueForTesting().length, 2, "events were dropped on failure");

  failNext = false;
  // Backoff is in force, so wait it out the way wall time would.
  await new Promise((resolve) => setTimeout(resolve, 2_100));
  await telemetry.flush();

  assert.equal(attempts.length, 2, "never retried");
  assert.equal(telemetry.queueForTesting().length, 0);
  telemetry.resetForTesting();
});

test("a retried event carries the same uuid so PostHog can collapse it", async () => {
  const attempts: Record<string, unknown>[][] = [];
  let failNext = true;
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d",
    flushThreshold: 1000,
    delivery: async (batch) => {
      attempts.push(batch);
      if (failNext) throw new Error("network down");
    },
  });

  telemetry.capture("once");
  await telemetry.flush();
  failNext = false;
  await new Promise((resolve) => setTimeout(resolve, 2_100));
  await telemetry.flush();

  assert.equal(attempts.length, 2);
  const first = attempts[0][0].uuid;
  assert.ok(first, "events carry no uuid, so a retry would double count");
  assert.equal(attempts[1][0].uuid, first, "retry minted a new uuid");
  telemetry.resetForTesting();
});

test("repeated failures back off instead of retrying every flush", async () => {
  let calls = 0;
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d",
    flushThreshold: 1000,
    delivery: async () => { calls += 1; throw new Error("blocked"); },
  });

  telemetry.capture("one");
  await telemetry.flush();
  await telemetry.flush();
  await telemetry.flush();

  assert.equal(calls, 1, "a blocked host was hammered on every flush");
  assert.equal(telemetry.queueForTesting().length, 1, "the event was lost while backing off");
  telemetry.resetForTesting();
});

test("a full queue drops the new event and keeps the batch being retried", async () => {
  // Python's record() refuses new events once the spool is full rather than
  // evicting the backlog. Keeping the newest here would throw away exactly the
  // events the retry exists to save.
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d",
    flushThreshold: 1000, maxQueueSize: 3,
    delivery: async () => { throw new Error("down"); },
  });

  telemetry.capture("a");
  telemetry.capture("b");
  await telemetry.flush();
  telemetry.capture("c");
  telemetry.capture("d");
  telemetry.capture("e");

  const events = telemetry.queueForTesting().map((e) => (e as any).event);
  assert.ok(events.length <= 3, "queue grew past maxQueueSize");
  assert.deepEqual(events.slice(0, 2), ["a", "b"], "the retried batch was evicted instead of the new events");
  telemetry.resetForTesting();
});

test("the exit-time flush ignores the backoff", async () => {
  // beforeExit is the last chance the process gets. Gating it on the same
  // cooldown meant that after any failure it did nothing and the queue died.
  let attempts = 0;
  let failing = true;
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d", flushThreshold: 1000,
    delivery: async () => { attempts += 1; if (failing) throw new Error("down"); },
  });

  telemetry.capture("a");
  await telemetry.flush();
  assert.equal(attempts, 1);

  failing = false;
  await telemetry.flush();
  assert.equal(attempts, 1, "the backoff should still hold for an ordinary flush");

  await telemetry.flush(true);
  assert.equal(attempts, 2, "the exit flush was suppressed by the backoff");
  assert.equal(telemetry.queueForTesting().length, 0);
  telemetry.resetForTesting();
});

test("every event carries a capture-time timestamp", async () => {
  const sent: Record<string, unknown>[][] = [];
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d", flushThreshold: 1000,
    delivery: async (batch) => { sent.push(batch); },
  });

  telemetry.capture("a");
  const capturedAt = Date.now();
  await new Promise((resolve) => setTimeout(resolve, 50));
  await telemetry.flush();

  const stamped = sent[0][0].timestamp as string;
  assert.ok(stamped, "no timestamp, so PostHog would record delivery time");
  assert.ok(Math.abs(Date.parse(stamped) - capturedAt) < 1_000, "not capture time");
  telemetry.resetForTesting();
});

test("a batch the server will never accept is eventually given up on", async () => {
  let attempts = 0;
  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d", flushThreshold: 1000,
    delivery: async () => { attempts += 1; throw new Error("permanently bad"); },
  });

  telemetry.capture("doomed");
  for (let i = 0; i < 8; i += 1) await telemetry.flush(true);

  assert.ok(attempts <= 6, `retried ${attempts} times with no cap`);
  assert.equal(telemetry.queueForTesting().length, 0, "a doomed batch held the queue forever");
  telemetry.resetForTesting();
});

test("an HTTP error response is a failure, not a delivery", async () => {
  // fetch only rejects on a network-level failure, so a 500 used to resolve
  // normally and the batch was dropped as delivered. Exercises the real default
  // delivery path rather than an injected one, which is where this hid.
  const realFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = (async () => {
    calls += 1;
    return new Response("upstream is unwell", { status: 503 });
  }) as typeof fetch;

  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d", flushThreshold: 1000,
  });
  try {
    telemetry.capture("during.outage");
    await telemetry.flush();

    assert.equal(calls, 1, "never reached the network");
    assert.equal(telemetry.queueForTesting().length, 1, "a 503 was counted as delivered");
  } finally {
    globalThis.fetch = realFetch;
    telemetry.resetForTesting();
  }
});

test("a 2xx is a delivery", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response("ok", { status: 200 })) as typeof fetch;

  const telemetry = createTelemetry({
    host: "h", source: "S", version: "1", distinctId: "d", flushThreshold: 1000,
  });
  try {
    telemetry.capture("fine");
    await telemetry.flush();
    assert.equal(telemetry.queueForTesting().length, 0, "a good response did not clear the queue");
  } finally {
    globalThis.fetch = realFetch;
    telemetry.resetForTesting();
  }
});
