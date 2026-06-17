/**
 * Plugin telemetry for the Mem0 OpenCode plugin — anonymous usage tracking
 * via PostHog.
 *
 * Emits the SAME event schema as the Mem0 editor plugin's telemetry.py
 * (event names prefixed `plugin.`, `source: "plugin"`, `platform: "opencode"`,
 * `distinct_id = sha256(apiKey)[:32]`) so OpenCode shows up as just another
 * `platform` value in the shared plugin dashboard instead of a separate
 * event namespace.
 *
 * Fire-and-forget: never throws, never blocks, failures are swallowed. Only
 * fires when an API key is present (same as the editor plugin — anonymous
 * installs without a key emit nothing). Disable with MEM0_TELEMETRY=false.
 *
 * Never sends: memory content, API keys, raw user/project IDs. Only sends:
 * event type, platform, plugin version, anonymized hash of the API key.
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";
const REQUEST_TIMEOUT_MS = 2_000;

function _loadPluginVersion(): string {
  // Source context: telemetry.ts sits next to package.json (./).
  // Bundled context: dist/index.js sits one level below it (../).
  for (const rel of ["./package.json", "../package.json"]) {
    try {
      const pkg = JSON.parse(readFileSync(new URL(rel, import.meta.url), "utf-8"));
      if (pkg?.name === "@mem0/opencode-plugin" && pkg.version) return pkg.version;
    } catch {
      /* try next candidate */
    }
  }
  return "unknown";
}

const PLUGIN_VERSION = _loadPluginVersion();

export function isTelemetryEnabled(): boolean {
  const val = process.env.MEM0_TELEMETRY;
  if (val === undefined) return true;
  const s = val.toLowerCase();
  return s !== "false" && s !== "0" && s !== "no" && s !== "off";
}

function distinctId(apiKey: string): string {
  // Matches telemetry.py `_distinct_id()` so the same user is one person in
  // PostHog whether they use OpenCode or any other Mem0 editor plugin.
  return createHash("sha256").update(apiKey).digest("hex").slice(0, 32);
}

/**
 * Build the PostHog event payload, or null when telemetry is disabled or no
 * API key is available. Pure (aside from env/version reads) and exported for
 * testing. System-controlled properties are applied last so a caller cannot
 * override `source`/`platform`/etc.
 */
export function buildEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
): Record<string, unknown> | null {
  if (!isTelemetryEnabled() || !apiKey) return null;
  return {
    api_key: POSTHOG_API_KEY,
    distinct_id: distinctId(apiKey),
    event: `plugin.${eventType}`,
    properties: {
      ...properties,
      source: "plugin",
      platform: "opencode",
      plugin_version: PLUGIN_VERSION,
      os: process.platform,
      sample_rate: 1.0,
      $process_person_profile: false,
      $lib: "posthog-node",
    },
  };
}

/** Send a usage event, fire-and-forget. Never throws, never blocks. */
export function captureEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
): void {
  const payload = buildEvent(eventType, properties, apiKey);
  if (!payload) return;
  try {
    void fetch(POSTHOG_HOST, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    }).catch(() => {
      /* fire-and-forget */
    });
  } catch {
    /* never throw */
  }
}
