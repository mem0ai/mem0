/**
 * Plugin telemetry — anonymous usage tracking via PostHog.
 *
 * Same format as the sibling Mem0 plugins (integrations/openclaw/telemetry.ts,
 * integrations/pi-agent-plugin/src/telemetry.ts): fire-and-forget, batched and
 * flushed every 5s or every 10 events, never throwing into the tool runner.
 * This copy exists because integrations are self-contained (no shared
 * toolchain); the three copies should be lifted into one shared helper package
 * — tracked as a follow-up, see the PR discussion.
 *
 * Disable with: MEM0_TELEMETRY=false
 */

import { createHash, randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

const FLUSH_INTERVAL_MS = 5_000;
const FLUSH_THRESHOLD = 10;

let eventQueue: Record<string, unknown>[] = [];
let flushTimer: ReturnType<typeof setInterval> | undefined;

function _loadPluginVersion(): string {
  try {
    const pkgUrl = new URL("../package.json", import.meta.url);
    const pkg = JSON.parse(fs.readFileSync(pkgUrl, "utf-8"));
    return pkg.version ?? "unknown";
  } catch {
    return "unknown";
  }
}

const PLUGIN_VERSION = _loadPluginVersion();

// ── Opt-out ──────────────────────────────────────────────────────────────

function isTelemetryEnabled(): boolean {
  try {
    const val = process.env.MEM0_TELEMETRY;
    if (val !== undefined) {
      const s = val.toLowerCase();
      return s !== "false" && s !== "0" && s !== "no" && s !== "off";
    }
    return true;
  } catch {
    return true;
  }
}

// ── Identity ─────────────────────────────────────────────────────────────

const TELEMETRY_ID_PATH = path.join(os.homedir(), ".mem0", "dsh-telemetry-id.json");

let _cachedAnonymousId: string | undefined;

function getOrCreateAnonymousId(): string {
  if (_cachedAnonymousId) return _cachedAnonymousId;
  try {
    if (fs.existsSync(TELEMETRY_ID_PATH)) {
      const data = JSON.parse(fs.readFileSync(TELEMETRY_ID_PATH, "utf-8"));
      if (data.anonymousId) {
        _cachedAnonymousId = data.anonymousId;
        return _cachedAnonymousId!;
      }
    }
  } catch {
    /* ignore */
  }

  const newId = `dsh-mem0-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    fs.mkdirSync(path.dirname(TELEMETRY_ID_PATH), { recursive: true });
    fs.writeFileSync(TELEMETRY_ID_PATH, JSON.stringify({ anonymousId: newId }), "utf-8");
  } catch {
    /* ignore — return generated id anyway */
  }
  _cachedAnonymousId = newId;
  return newId;
}

function getDistinctId(apiKey?: string): string {
  if (apiKey) {
    return createHash("sha256").update(apiKey).digest("hex");
  }
  return getOrCreateAnonymousId();
}

// ── Flush machinery ──────────────────────────────────────────────────────

function ensureFlushTimer(): void {
  if (flushTimer) return;
  flushTimer = setInterval(flushEvents, FLUSH_INTERVAL_MS);
  if (typeof flushTimer === "object" && "unref" in flushTimer) {
    flushTimer.unref();
  }
}

let _exitHandlerInstalled = false;

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

// ── Public API ───────────────────────────────────────────────────────────

export function captureEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
  ctx?: { apiKey?: string },
): void {
  if (!isTelemetryEnabled()) return;

  try {
    const distinctId = getDistinctId(ctx?.apiKey);

    eventQueue.push({
      event: eventName,
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

    ensureFlushTimer();
    ensureExitHandler();

    if (eventQueue.length >= FLUSH_THRESHOLD) {
      flushEvents();
    }
  } catch {
    /* silently swallow */
  }
}

export function captureToolEvent(
  action: string,
  properties: Record<string, unknown> = {},
  ctx?: { apiKey?: string },
): void {
  captureEvent("dsh.tool.mem0", { action, ...properties }, ctx);
}

// ── Test helpers ─────────────────────────────────────────────────────────

export function _getEventQueue(): Record<string, unknown>[] {
  return eventQueue;
}

export function _resetForTesting(): void {
  eventQueue = [];
  if (flushTimer) {
    clearInterval(flushTimer);
    flushTimer = undefined;
  }
  _cachedAnonymousId = undefined;
}
