/**
 * Plugin telemetry — anonymous usage tracking via PostHog.
 *
 * Sends fire-and-forget events to PostHog using native fetch().
 * Events are batched and flushed every 5 seconds or when the queue
 * reaches 10 events, whichever comes first.
 *
 * Disable with: MEM0_TELEMETRY=false
 */

import { createHash, randomUUID } from "node:crypto";
import { readPluginAuth, writePluginAuth, getBaseUrl, clearAnonymousTelemetryId } from "./cli/config-file.ts";

declare const __OPENCLAW_PLUGIN_VERSION__: string;
export const PLUGIN_VERSION: string = __OPENCLAW_PLUGIN_VERSION__;

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

const FLUSH_INTERVAL_MS = 5_000;
const FLUSH_THRESHOLD = 10;

let eventQueue: Record<string, unknown>[] = [];
let flushTimer: ReturnType<typeof setInterval> | undefined;

let _cachedAnonymousId: string | undefined;
let _aliasCheckDone = false;

/**
 * Return a persistent per-machine anonymous ID, generating one if needed.
 *
 * Stored in ~/.openclaw/openclaw.json under the plugin's `anonymousTelemetryId`
 * field so repeat sessions on the same machine share one PostHog identity
 * instead of collapsing into a single shared fallback string. The result is
 * cached in module memory after the first read so we don't re-touch disk on
 * every queued event.
 */
function getOrCreateAnonymousId(): string {
  if (_cachedAnonymousId) return _cachedAnonymousId;
  try {
    const auth = readPluginAuth();
    if (auth.anonymousTelemetryId) {
      _cachedAnonymousId = auth.anonymousTelemetryId;
      return _cachedAnonymousId;
    }
  } catch {
    /* ignore */
  }
  const newId = `openclaw-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    writePluginAuth({ anonymousTelemetryId: newId });
  } catch {
    /* ignore — return generated id anyway */
  }
  _cachedAnonymousId = newId;
  return newId;
}

/**
 * If we just resolved to a real identity but a stored anonymous id exists,
 * build a one-shot PostHog $identify event so the pre-signup history gets
 * stitched onto the authenticated profile. Returns null when no aliasing is
 * needed (already done, or no anon id on disk, or still anonymous).
 *
 * Caller is responsible for pushing the returned event onto eventQueue ahead
 * of the regular event.
 */
function maybeBuildIdentifyEvent(
  distinctId: string,
): Record<string, unknown> | null {
  if (_aliasCheckDone) return null;
  if (!distinctId || distinctId.startsWith("openclaw-anon-")) return null;
  try {
    const auth = readPluginAuth();
    const storedAnon = auth.anonymousTelemetryId;
    if (!storedAnon) {
      _aliasCheckDone = true;
      return null;
    }
    const identifyEvent = {
      event: "$identify",
      distinct_id: distinctId,
      properties: {
        $anon_distinct_id: storedAnon,
        $lib: "posthog-node",
      },
    };
    // Clear the anonymous ID from config after aliasing (don't write empty string)
    try {
      clearAnonymousTelemetryId();
    } catch {
      /* ignore — alias may double-fire next session, harmless */
    }
    _aliasCheckDone = true;
    _cachedAnonymousId = undefined;
    return identifyEvent;
  } catch {
    return null;
  }
}

let _emailResolutionAttempted = false;

/**
 * If we have an apiKey but no cached userEmail, do a one-shot /v1/ping/
 * call to resolve the email and cache it. This runs async as a side-effect;
 * the current event ships with md5(apiKey) but subsequent events (including
 * those flushed by the beforeExit handler in the same process) will use
 * the resolved email.
 */
function maybeResolveEmail(apiKey: string): void {
  if (_emailResolutionAttempted) return;
  _emailResolutionAttempted = true;

  const baseUrl = getBaseUrl().replace(/\/+$/, "");
  fetch(`${baseUrl}/v1/ping/`, {
    method: "GET",
    headers: {
      Authorization: `Token ${apiKey}`,
      "Content-Type": "application/json",
    },
    signal: AbortSignal.timeout(5_000),
  })
    .then((res) => res.json())
    .then((data: any) => {
      const email = data?.user_email;
      if (email) {
        try {
          writePluginAuth({ userEmail: email });
        } catch {
          /* ignore */
        }
        const oldId = createHash("sha256").update(apiKey).digest("hex");
        const newId = createHash("sha256").update(email).digest("hex");
        for (const ev of eventQueue) {
          if (ev.distinct_id === oldId) {
            ev.distinct_id = newId;
          }
        }
      }
    })
    .catch(() => {
      /* silently swallow — md5(apiKey) is used as fallback */
    });
}

let _telemetryEnabled: boolean | undefined;
function isTelemetryEnabled(): boolean {
  if (_telemetryEnabled !== undefined) return _telemetryEnabled;
  try {
    const val = (globalThis as any).__mem0_telemetry_override;
    if (val !== undefined) {
      const s = String(val).toLowerCase();
      _telemetryEnabled = s !== "false" && s !== "0" && s !== "no";
    } else {
      _telemetryEnabled = true;
    }
  } catch {
    _telemetryEnabled = true;
  }
  return _telemetryEnabled;
}

/**
 * Return a stable anonymous identifier for the current user.
 *
 * Priority: cached userEmail (from /v1/ping/) > MD5(apiKey) >
 * persistent per-machine anonymous ID.
 */
function getDistinctId(apiKey?: string): string {
  try {
    const auth = readPluginAuth();
    if (auth.userEmail) {
      return createHash("sha256").update(auth.userEmail).digest("hex");
    }
  } catch {
    /* ignore */
  }
  if (apiKey) {
    return createHash("sha256").update(apiKey).digest("hex");
  }
  return getOrCreateAnonymousId();
}

function ensureFlushTimer(): void {
  if (flushTimer) return;
  flushTimer = setInterval(flushEvents, FLUSH_INTERVAL_MS);
  if (typeof flushTimer === "object" && "unref" in flushTimer) {
    flushTimer.unref();
  }
}

let _exitHandlerInstalled = false;

/**
 * Install a one-time `beforeExit` handler that drains queued events on
 * process exit. Without this, short-lived CLI invocations (e.g. one
 * `openclaw mem0 status` call) exit before the unref'd flushTimer fires
 * and before FLUSH_THRESHOLD is hit, dropping every queued event silently.
 *
 * Returning a Promise from a `beforeExit` handler keeps the event loop
 * alive until that Promise resolves, so the awaited fetch actually has
 * time to land at PostHog.
 */
function ensureExitHandler(): void {
  if (_exitHandlerInstalled) return;
  _exitHandlerInstalled = true;
  process.on("beforeExit", async () => {
    if (eventQueue.length === 0) return;
    const batch = eventQueue;
    eventQueue = [];
    const body = JSON.stringify({ api_key: POSTHOG_API_KEY, batch });
    try {
      await fetch(POSTHOG_HOST, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": String(Buffer.byteLength(body)),
        },
        body,
        signal: AbortSignal.timeout(3_000),
      });
    } catch {
      /* silently swallow */
    }
  });
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

    let hasEmail = false;
    try { hasEmail = !!readPluginAuth().userEmail; } catch { /* ignore */ }
    if (ctx?.apiKey && !hasEmail && !distinctId.startsWith("openclaw-anon-")) {
      maybeResolveEmail(ctx.apiKey);
    }

    // First authenticated event after a previous anonymous session: queue a
    // $identify ahead of the regular event so PostHog merges the anonymous
    // history onto the authenticated profile in the same batch flush.
    const identifyEvent = maybeBuildIdentifyEvent(distinctId);
    if (identifyEvent) {
      eventQueue.push(identifyEvent);
    }

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
    ensureExitHandler();

    if (eventQueue.length >= FLUSH_THRESHOLD) {
      flushEvents();
    }
  } catch {
    /* silently swallow */
  }
}
