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

export function createTelemetry(config: TelemetryConfig) {
  let queue: Record<string, unknown>[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
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
    const batch = queue;
    queue = [];
    try {
      await deliver(batch);
    } catch {
      // Telemetry must never affect plugin behavior.
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
    if (timer) clearInterval(timer);
    timer = undefined;
    process.off("beforeExit", beforeExit);
  }

  return { build, capture, flush, resetForTesting, queueForTesting: () => queue };
}
