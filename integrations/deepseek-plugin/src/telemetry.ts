/**
 * Anonymous usage telemetry for the DeepSeek Harness plugin.
 *
 * Fire-and-forget PostHog events over native fetch, batched and flushed every
 * 5 seconds, at 10 queued events, or on process exit. Never throws, never logs.
 *
 * Events carry only tool names, durations, counts, and coarse failure kinds:
 * never queries, memory text, filters, or API keys.
 *
 * Disable with MEM0_TELEMETRY=false.
 */
import { randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_BATCH_URL = "https://us.i.posthog.com/batch/";
const FLUSH_INTERVAL_MS = 5_000;
const FLUSH_THRESHOLD = 10;
const SEND_TIMEOUT_MS = 3_000;

const PLUGIN_VERSION = ((): string => {
  try {
    return JSON.parse(
      fs.readFileSync(new URL("../package.json", import.meta.url), "utf-8"),
    ).version;
  } catch {
    return "unknown";
  }
})();

/** The Mem0 SDK resolves this to the account email once ping() lands, so events join other Mem0 surfaces. */
export interface TelemetryIdentity {
  telemetryId?: string;
}

let queue: Record<string, unknown>[] = [];
let flushTimer: ReturnType<typeof setInterval> | undefined;
let exitHandlerInstalled = false;
let cachedAnonymousId: string | undefined;
let identified = false;

function identityPath(): string {
  return path.join(os.homedir(), ".mem0", "deepseek-plugin-telemetry.json");
}

export function isTelemetryEnabled(): boolean {
  const value = process.env.MEM0_TELEMETRY?.toLowerCase();
  return value !== "false" && value !== "0" && value !== "no" && value !== "off";
}

function anonymousId(): string {
  if (cachedAnonymousId) return cachedAnonymousId;
  try {
    const stored = JSON.parse(fs.readFileSync(identityPath(), "utf-8"));
    if (typeof stored.anonymousId === "string" && stored.anonymousId) {
      cachedAnonymousId = stored.anonymousId;
      return cachedAnonymousId!;
    }
  } catch {
    /* first run, or an unreadable identity file */
  }
  const created = `deepseek-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    const target = identityPath();
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify({ anonymousId: created }), "utf-8");
  } catch {
    /* an unwritable home directory must not break the plugin */
  }
  cachedAnonymousId = created;
  return created;
}

/** Merge the pre-ping anonymous history into the account once the email resolves. */
function identifyEvent(distinctId: string): Record<string, unknown> | undefined {
  if (identified || distinctId.startsWith("deepseek-anon-")) return undefined;
  identified = true;
  let storedAnonymousId: string | undefined;
  try {
    storedAnonymousId = JSON.parse(fs.readFileSync(identityPath(), "utf-8")).anonymousId;
    fs.unlinkSync(identityPath());
  } catch {
    return undefined;
  }
  cachedAnonymousId = undefined;
  if (!storedAnonymousId) return undefined;
  return {
    event: "$identify",
    distinct_id: distinctId,
    properties: { $anon_distinct_id: storedAnonymousId, $lib: "posthog-node" },
  };
}

export function flushEvents(): void {
  if (queue.length === 0) return;
  const batch = queue;
  queue = [];
  fetch(POSTHOG_BATCH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: POSTHOG_API_KEY, batch }),
    signal: AbortSignal.timeout(SEND_TIMEOUT_MS),
  }).catch(() => {
    /* telemetry never surfaces its own failures */
  });
}

function scheduleFlush(): void {
  if (!flushTimer) {
    flushTimer = setInterval(flushEvents, FLUSH_INTERVAL_MS);
    flushTimer.unref?.();
  }
  if (!exitHandlerInstalled) {
    exitHandlerInstalled = true;
    process.on("beforeExit", flushEvents);
  }
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

export function captureEvent(
  event: string,
  properties: Record<string, unknown>,
  client: TelemetryIdentity,
): void {
  if (!isTelemetryEnabled()) return;
  try {
    const distinctId = client.telemetryId || anonymousId();
    const identify = identifyEvent(distinctId);
    if (identify) queue.push(identify);
    queue.push({
      event,
      distinct_id: distinctId,
      properties: {
        source: "DEEPSEEK_HARNESS",
        language: "node",
        plugin_version: PLUGIN_VERSION,
        node_version: process.version,
        os: process.platform,
        $process_person_profile: false,
        $lib: "posthog-node",
        ...properties,
      },
    });
    scheduleFlush();
    if (queue.length >= FLUSH_THRESHOLD) flushEvents();
  } catch {
    /* telemetry never breaks a tool call */
  }
}

export function _queueForTesting(): Record<string, unknown>[] {
  return queue;
}

export function _resetForTesting(): void {
  queue = [];
  clearInterval(flushTimer);
  flushTimer = undefined;
  cachedAnonymousId = undefined;
  identified = false;
}
