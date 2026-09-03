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
  source: "plugin",
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

function projectHash(projectId?: string): Record<string, string> {
  return projectId ? { project_hash: createHash("sha256").update(projectId).digest("hex") } : {};
}

export function buildEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
  projectId?: string,
): Record<string, unknown> | null {
  currentDistinctId = apiKey ? distinctId(apiKey) : "";
  const event = telemetry.build(eventType, { ...properties, ...projectHash(projectId) });
  return event ? { api_key: POSTHOG_API_KEY, ...event } : null;
}

export function captureEvent(
  eventType: string,
  properties: Record<string, unknown>,
  apiKey: string | undefined,
  projectId?: string,
): void {
  currentDistinctId = apiKey ? distinctId(apiKey) : "";
  telemetry.capture(eventType, { ...properties, ...projectHash(projectId) });
}
