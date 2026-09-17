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

export function createTelemetry(config: TelemetryConfig) {
  let queue: Record<string, unknown>[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
  let consecutiveFailures = 0;
  let retryNotBefore = 0;
  const flushThreshold = config.flushThreshold ?? 10;
  const maxQueueSize = config.maxQueueSize ?? 100;

  const deliver = config.delivery ?? (async (batch: Record<string, unknown>[]) => {
    await fetch(POSTHOG_BATCH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: POSTHOG_API_KEY, batch }),
      signal: AbortSignal.timeout(3_000),
    });
  });

  async function flush(): Promise<void> {
    if (!queue.length) return;
    if (Date.now() < retryNotBefore) return;
    const batch = queue;
    queue = [];
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
      // Bounded by maxQueueSize and biased to the newest, matching capture():
      // a long outage costs the oldest events rather than unbounded memory.
      queue = [...batch, ...queue].slice(-maxQueueSize);
      consecutiveFailures += 1;
      retryNotBefore = Date.now() + Math.min(2 ** consecutiveFailures * 1_000, RETRY_BACKOFF_CEILING_MS);
    }
  }

  function beforeExit(): void {
    void flush();
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
      queue.push(payload);
      if (queue.length > maxQueueSize) queue = queue.slice(-maxQueueSize);
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
