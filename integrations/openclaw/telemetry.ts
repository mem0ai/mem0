import { createHash, randomUUID } from "node:crypto";

import { createTelemetry } from "../agent-plugins/core/typescript/src/telemetry.ts";
import { clearAnonymousTelemetryId, getBaseUrl, readPluginAuth, writePluginAuth } from "./cli/config-file.ts";

declare const __OPENCLAW_PLUGIN_VERSION__: string;
export const PLUGIN_VERSION: string = __OPENCLAW_PLUGIN_VERSION__;

let cachedAnonymousId: string | undefined;
let aliasCheckDone = false;
let emailResolutionAttempted = false;
let currentDistinctId = "";

function enabled(): boolean {
  const value = (globalThis as any).__mem0_telemetry_override ?? process.env.MEM0_TELEMETRY;
  return value === undefined || !["false", "0", "no", "off"].includes(String(value).toLowerCase());
}

function anonymousId(): string {
  if (cachedAnonymousId) return cachedAnonymousId;
  try {
    const stored = readPluginAuth().anonymousTelemetryId;
    if (stored) return (cachedAnonymousId = stored);
  } catch {
    // First run or unreadable config.
  }
  const created = `openclaw-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    writePluginAuth({ anonymousTelemetryId: created });
  } catch {
    // An unwritable config must not break the plugin.
  }
  return (cachedAnonymousId = created);
}

function distinctId(apiKey?: string): string {
  try {
    const email = readPluginAuth().userEmail;
    if (email) return createHash("sha256").update(email).digest("hex");
  } catch {
    // Fall through to the API key or anonymous identity.
  }
  return apiKey ? createHash("sha256").update(apiKey).digest("hex") : anonymousId();
}

const telemetry = createTelemetry({
  host: "openclaw",
  source: "OPENCLAW",
  version: PLUGIN_VERSION,
  distinctId: () => currentDistinctId,
  enabled,
});

function identifyAnonymous(id: string): void {
  if (aliasCheckDone || id.startsWith("openclaw-anon-")) return;
  try {
    const anonymous = readPluginAuth().anonymousTelemetryId;
    aliasCheckDone = true;
    if (!anonymous) return;
    telemetry.capture("$identify", { $anon_distinct_id: anonymous });
    clearAnonymousTelemetryId();
    cachedAnonymousId = undefined;
  } catch {
    // Aliasing is best effort.
  }
}

function resolveEmail(apiKey: string): void {
  if (emailResolutionAttempted) return;
  emailResolutionAttempted = true;
  fetch(`${getBaseUrl().replace(/\/+$/, "")}/v1/ping/`, {
    method: "GET",
    headers: { Authorization: `Token ${apiKey}`, "Content-Type": "application/json" },
    signal: AbortSignal.timeout(5_000),
  })
    .then((response) => response.json())
    .then((data: any) => {
      if (!data?.user_email) return;
      writePluginAuth({ userEmail: data.user_email });
      const oldId = createHash("sha256").update(apiKey).digest("hex");
      const newId = createHash("sha256").update(data.user_email).digest("hex");
      for (const event of telemetry.queueForTesting()) {
        if (event.distinct_id === oldId) event.distinct_id = newId;
      }
    })
    .catch(() => {
      // The API-key hash remains a stable fallback.
    });
}

export function captureEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
  context?: { apiKey?: string; mode?: string; skillsActive?: boolean },
): void {
  if (!enabled()) return;
  try {
    currentDistinctId = distinctId(context?.apiKey);
    let hasEmail = false;
    try {
      hasEmail = Boolean(readPluginAuth().userEmail);
    } catch {
      // Resolve it below when possible.
    }
    if (context?.apiKey && !hasEmail) resolveEmail(context.apiKey);
    identifyAnonymous(currentDistinctId);
    telemetry.capture(eventName, {
      mode: context?.mode,
      skills_active: context?.skillsActive,
      ...properties,
    });
  } catch {
    // Telemetry must never affect plugin behavior.
  }
}
