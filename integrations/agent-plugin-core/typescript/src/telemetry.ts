import { randomUUID } from "node:crypto";

import { redactSecrets } from "./lifecycle.ts";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_BATCH_URL = "https://us.i.posthog.com/batch/";
const OFF_VALUES = new Set(["false", "0", "no", "off"]);
const PRIVATE_KEYS = new Set([
  "apikey",
  "authorization",
  "password",
  "query",
  "secret",
  "prompt",
  "token",
  "text",
  "memory",
  "message",
  "error",
  "path",
  "cwd",
  "userid",
  "agentid",
  "runid",
  "repoid",
  "repositoryid",
  "projectid",
  "appid",
  "filters",
]);

export interface TelemetryConfig {
  host: string;
  source: string;
  version: string;
  distinctId: string | (() => string | undefined);
  delivery?: (batch: Record<string, unknown>[]) => void | Promise<void>;
  flushThreshold?: number;
  flushIntervalMs?: number;
  maxQueueSize?: number;
  commonProperties?: Record<string, unknown>;
  eventName?: (event: string) => string;
  enabled?: () => boolean;
}

export function isTelemetryEnabled(): boolean {
  const value = process.env.MEM0_TELEMETRY;
  return value === undefined || !OFF_VALUES.has(value.toLowerCase());
}

function safeValue(value: unknown): unknown {
  if (typeof value === "string") return redactSecrets(value);
  if (Array.isArray(value)) return value.map(safeValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !PRIVATE_KEYS.has(key.toLowerCase().replace(/[^a-z]/g, "")))
        .map(([key, nested]) => [key, safeValue(nested)]),
    );
  }
  return value;
}

function safeProperties(properties: Record<string, unknown>): Record<string, unknown> {
  return safeValue(properties) as Record<string, unknown>;
}

export function errorKind(error: unknown): string {
  const text = (error instanceof Error ? error.message : String(error)).toLowerCase();
  if (text.includes("timeout") || text.includes("aborted")) return "timeout";
  if (text.includes("401") || text.includes("403") || text.includes("unauthor")) return "auth";
  if (text.includes("429") || text.includes("rate limit")) return "rate-limited";
  if (/50[0234]/.test(text)) return "server-error";
  if (text.includes("400") || text.includes("422")) return "bad-request";
  if (text.includes("fetch failed") || text.includes("enotfound")) return "network";
  return error instanceof Error ? error.constructor.name : "other";
}

// Delivery is retried in memory, not spooled to disk, and that is a decision
// rather than an omission. The Python core spools because its hooks are separate
// processes that fire per tool call and exit immediately, so nothing survives
// without a file. These plugins are loaded into a host that lives for a whole
// session, so re-queueing covers the same transient failures without the claim
// and lease machinery a correct cross-process spool needs. What that leaves
// uncovered is narrow: a session that both starts and ends with no connectivity.
const RETRY_BACKOFF_CEILING_MS = 60_000;
// Consecutive failed flushes before the queue is dropped. Deliberately NOT the
// same thing as Python's budget, which rides in the claim filename and so
// follows one batch: this counter lives in the closure and counts the outage,
// not the payload. Events captured between attempts join the same queue and go
// with it. Per-batch accounting would need an attempt count on every event, and
// the queue is already bounded, so the simpler rule is the one in force here.
// Without any bound a payload the server will never accept is retried for the
// whole session and, now that the backlog is preferred over new events, holds
// the queue against everything behind it.
const MAX_DELIVERY_ATTEMPTS = 5;

export function createTelemetry(config: TelemetryConfig) {
  let queue: Record<string, unknown>[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
  let consecutiveFailures = 0;
  let retryNotBefore = 0;
  let exitFlushAttempted = false;
  let flushing = false;
  const flushThreshold = config.flushThreshold ?? 10;
  const maxQueueSize = config.maxQueueSize ?? 100;

  const deliver = config.delivery ?? (async (batch: Record<string, unknown>[]) => {
    const response = await fetch(POSTHOG_BATCH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: POSTHOG_API_KEY, batch }),
      signal: AbortSignal.timeout(3_000),
    });
    // fetch only rejects on a network-level failure. Without this check a 500,
    // a 503 or a 429 resolved normally and the batch was counted as delivered
    // and dropped, which is the likelier outage than a refused connection.
    // Any non-2xx is retried, matching the Python core: the backoff and the
    // queue bound contain a payload that will never be accepted, because the
    // re-queued batch sits at the front and is the first thing evicted.
    if (!response.ok) throw new Error(`posthog responded ${response.status}`);
  });

  async function flush(force = false): Promise<void> {
    // One at a time. Two overlapping flushes each detach the queue and each
    // prepend their own batch back on failure, so the later batch lands in front
    // of the earlier one and the truncation then drops the OLDER events first,
    // inverting the priority the failure path exists to establish. A second
    // caller returns immediately; the queue waits for the next flush.
    if (flushing) return;
    if (!queue.length) return;
    // `force` skips the cooldown. beforeExit is the last chance this process
    // gets, and gating it on the same backoff meant that after any failure the
    // exit flush did nothing and the queue died with the process, which is the
    // loss this whole mechanism exists to prevent.
    if (!force && Date.now() < retryNotBefore) return;
    const batch = queue;
    queue = [];
    flushing = true;
    try {
      await deliver(batch);
      consecutiveFailures = 0;
      retryNotBefore = 0;
    } catch {
      // Put it back. Detaching the batch and swallowing the error deleted the
      // events outright, so any blip silently dropped telemetry with nothing
      // recording that it had happened. Every event carries a uuid, so a retry
      // that duplicates one PostHog already accepted is collapsed there.
      //
      consecutiveFailures += 1;
      if (consecutiveFailures >= MAX_DELIVERY_ATTEMPTS) {
        // Give up on the queue so a failing outage cannot hold it for the
        // session. This drops whatever is queued now, which includes events
        // captured during the outage, not only the batch that kept failing.
        consecutiveFailures = 0;
        retryNotBefore = 0;
        return;
      }
      // Keep the FRONT on overflow, so the batch being retried survives and a
      // new event is what gets dropped. Matches the Python core, where record()
      // refuses new events once the spool is full rather than evicting the
      // backlog. Keeping the newest would throw away exactly the events this
      // retry exists to save.
      queue = [...batch, ...queue].slice(0, maxQueueSize);
      retryNotBefore = Date.now() + Math.min(2 ** consecutiveFailures * 1_000, RETRY_BACKOFF_CEILING_MS);
    } finally {
      flushing = false;
    }
  }

  function beforeExit(): void {
    // Once, and only once. Node re-emits beforeExit whenever the handler
    // schedules more async work, so an unconditional forced flush looped until
    // the attempt budget was spent: five attempts against a 3s delivery timeout
    // is fifteen seconds added to the shutdown of whatever editor or CLI is
    // hosting this. The backoff used to end that loop after one attempt, and
    // removing it for the forced path removed the only thing bounding it.
    if (exitFlushAttempted) return;
    exitFlushAttempted = true;
    void flush(true);
  }

  function build(event: string, properties: Record<string, unknown> = {}): Record<string, unknown> | null {
    if (!(config.enabled?.() ?? isTelemetryEnabled())) return null;
    try {
      const distinctId = typeof config.distinctId === "function" ? config.distinctId() : config.distinctId;
      if (!distinctId) return null;
      return {
        event: config.eventName?.(event) ?? event,
        distinct_id: distinctId,
        // Stamped once, at capture. This is what makes retrying safe: a batch
        // re-sent after a failure carries the same ids, so PostHog collapses
        // anything it already accepted instead of counting it twice.
        uuid: randomUUID(),
        // Capture time, not ingestion time. Events now sit through backoff and
        // across a whole outage, so without this PostHog records them whenever
        // delivery happened to succeed. It also matters for the uuid dedupe
        // above, whose key includes the event date.
        timestamp: new Date().toISOString(),
        properties: {
          ...safeProperties(properties),
          ...safeProperties(config.commonProperties ?? {}),
          host: config.host,
          source: config.source,
          language: "node",
          plugin_version: config.version,
          node_version: process.version,
          os: process.platform,
          $process_person_profile: false,
          $lib: "posthog-node",
        },
      };
    } catch {
      return null;
    }
  }

  function capture(event: string, properties: Record<string, unknown> = {}): void {
    try {
      const payload = build(event, properties);
      if (!payload) return;
      // Full means drop this event, not evict the backlog. Same rule as the
      // failure path above and as Python's record().
      if (queue.length >= maxQueueSize) return;
      queue.push(payload);
      if (!timer) {
        timer = setInterval(() => void flush(), config.flushIntervalMs ?? 5_000);
        timer.unref?.();
        process.on("beforeExit", beforeExit);
      }
      if (queue.length >= flushThreshold) void flush();
    } catch {
      // Telemetry must never affect plugin behavior.
    }
  }

  function resetForTesting(): void {
    queue = [];
    consecutiveFailures = 0;
    retryNotBefore = 0;
    if (timer) clearInterval(timer);
    timer = undefined;
    process.off("beforeExit", beforeExit);
  }

  return { build, capture, flush, resetForTesting, queueForTesting: () => queue };
}
