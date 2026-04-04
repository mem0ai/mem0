/**
 * Plugin telemetry — anonymous usage tracking via PostHog.
 *
 * Sends fire-and-forget events to PostHog using native fetch().
 * Events are batched and flushed every 5 seconds or when the queue
 * reaches 10 events, whichever comes first.
 *
 * Disable with: MEM0_TELEMETRY=false
 */

import { createHash } from "node:crypto";
import { readPluginAuth } from "./cli/config-file.ts";

export const PLUGIN_VERSION = "1.0.4";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

const FLUSH_INTERVAL_MS = 5_000;
const FLUSH_THRESHOLD = 10;

let eventQueue: Record<string, unknown>[] = [];
let flushTimer: ReturnType<typeof setInterval> | undefined;

function isTelemetryEnabled(): boolean {
  const val = (process.env.MEM0_TELEMETRY ?? "true").toLowerCase();
  return val !== "false" && val !== "0" && val !== "no";
}

/**
 * Return a stable anonymous identifier for the current user.
 *
 * Priority: cached userEmail (from /v1/ping/) > MD5(apiKey) > fallback.
 */
function getDistinctId(apiKey?: string): string {
  try {
    const auth = readPluginAuth();
    if (auth.userEmail) return auth.userEmail;
  } catch {
    /* ignore */
  }
  if (apiKey) {
    return createHash("md5").update(apiKey).digest("hex");
  }
  return "anonymous-openclaw";
}

function ensureFlushTimer(): void {
  if (flushTimer) return;
  flushTimer = setInterval(flushEvents, FLUSH_INTERVAL_MS);
  if (typeof flushTimer === "object" && "unref" in flushTimer) {
    flushTimer.unref();
  }
}

function flushEvents(): void {
  if (eventQueue.length === 0) return;
  const batch = eventQueue;
  eventQueue = [];

  const body = JSON.stringify({ api_key: POSTHOG_API_KEY, batch });
  fetch(POSTHOG_HOST, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": String(Buffer.byteLength(body)),
    },
    body,
    signal: AbortSignal.timeout(3_000),
  }).catch(() => {
    /* silently swallow */
  });
}

/**
 * Capture a PostHog event (non-blocking, never throws).
 */
export function captureEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
  ctx?: { apiKey?: string; mode?: string; skillsActive?: boolean },
): void {
  if (!isTelemetryEnabled()) return;

  try {
    const distinctId = getDistinctId(ctx?.apiKey);

    eventQueue.push({
      event: eventName,
      distinct_id: distinctId,
      properties: {
        source: "OPENCLAW",
        language: "node",
        plugin_version: PLUGIN_VERSION,
        node_version: process.version,
        os: process.platform,
        mode: ctx?.mode,
        skills_active: ctx?.skillsActive,
        $process_person_profile: false,
        $lib: "posthog-node",
        ...properties,
      },
    });

    ensureFlushTimer();

    if (eventQueue.length >= FLUSH_THRESHOLD) {
      flushEvents();
    }
  } catch {
    /* silently swallow */
  }
}
