import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { release } from "node:os";

import {
  createTelemetry,
  isTelemetryEnabled,
} from "../agent-plugin-core/typescript/src/telemetry.ts";

export { isTelemetryEnabled };

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const PLUGIN_VERSION = (() => {
  for (const relative of ["./package.json", "../package.json"]) {
    try {
      const pkg = JSON.parse(readFileSync(new URL(relative, import.meta.url), "utf-8"));
      if (pkg?.name === "@mem0/opencode-plugin" && pkg.version) return pkg.version;
    } catch {
      // Try the source or bundled location.
    }
  }
  return "unknown";
})();

let currentDistinctId = "";
const telemetry = createTelemetry({
  host: "opencode",
  // Shaped like the platform's EventSource values, as every other surface is.
  // "plugin" said nothing about which plugin and matched no vocabulary.
  source: "OPENCODE_PLUGIN",
  version: PLUGIN_VERSION,
  distinctId: () => currentDistinctId,
  eventName: (event) => `plugin.${event}`,
  commonProperties: {
    platform: "opencode",
    os_version: release(),
    sample_rate: 1.0,
  },
});

function distinctId(apiKey: string): string {
  return createHash("sha256").update(apiKey).digest("hex").slice(0, 32);
}

/**
 * Salted so the hash is not enumerable.
 *
 * An unsalted SHA-256 of a project id is reversible by anyone who can guess the
 * id, which for a project identifier is a small space. The API key is the salt:
 * it is already in play here (distinctId is a digest of it), it is high entropy,
 * and using it needs no per-install file and so no write race to get wrong. The
 * hash is therefore per account rather than per machine, which also keeps joins
 * working for one user across machines. It resets when the key rotates, which is
 * consistent, because distinctId resets with it.
 *
 * Both are omitted without a key. An event cannot be built without a distinctId
 * anyway, so this costs nothing.
 */
function projectHash(projectId?: string, apiKey?: string): Record<string, string> {
  if (!projectId || !apiKey) return {};
  return { project_hash: createHash("sha256").update(`${apiKey}:${projectId}`).digest("hex") };
}

export function buildEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
  projectId?: string,
): Record<string, unknown> | null {
  currentDistinctId = apiKey ? distinctId(apiKey) : "";
  const event = telemetry.build(eventType, { ...properties, ...projectHash(projectId, apiKey) });
  return event ? { api_key: POSTHOG_API_KEY, ...event } : null;
}

export function captureEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
  projectId?: string,
): void {
  currentDistinctId = apiKey ? distinctId(apiKey) : "";
  telemetry.capture(eventType, { ...properties, ...projectHash(projectId, apiKey) });
}
