import { createHash, randomUUID } from "node:crypto";

import { createTelemetry } from "../agent-plugin-core/typescript/src/telemetry.ts";
import {
  clearAnonymousTelemetryId,
  clearResolvedAccount,
  getBaseUrl,
  readPluginAuth,
  writePluginAuth,
} from "./cli/config-file.ts";

declare const __OPENCLAW_PLUGIN_VERSION__: string;
export const PLUGIN_VERSION: string = __OPENCLAW_PLUGIN_VERSION__;

let cachedAnonymousId: string | undefined;
let aliasCheckDone = false;
let resolutionAttemptedFor = "";
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

/** SHA-256 prefix of the key an account was resolved for. */
function keyFingerprint(apiKey?: string): string {
  return apiKey ? createHash("sha256").update(apiKey).digest("hex").slice(0, 16) : "";
}

function distinctId(apiKey?: string): string {
  try {
    const auth = readPluginAuth();
    if (auth.userEmail) {
      // Only when it belongs to the key in hand. Without this check a cached
      // email was used forever: switch to a different account and every event
      // kept reporting under the previous one, with nothing to notice it by.
      if (auth.keyFingerprint === keyFingerprint(apiKey)) {
        return createHash("sha256").update(auth.userEmail).digest("hex");
      }
      // Only a REAL key that disagrees means the account changed. Without the
      // apiKey guard the comparison is `undefined === ""` for any call that
      // simply omits the key, so a capture with no context wiped a perfectly
      // good account out of openclaw.json.
      //
      // A row with an email and NO fingerprint is the legacy shape, from an
      // install predating this field. Clearing it here deleted a real account
      // before anything had replaced it, and if the re-resolve then failed
      // because the user was offline the email was gone from disk for good. The
      // Python core refuses the same trade: verify, and keep what you have until
      // the verification succeeds. resolveEmail below overwrites both fields
      // when it does, so there is nothing to clear first.
      if (apiKey && auth.keyFingerprint) clearResolvedAccount();
    }
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
  // Latched per key, not once per process. A single boolean meant a key changed
  // mid-session was never looked up, so the fallback identity stuck until restart.
  const fingerprint = keyFingerprint(apiKey);
  if (resolutionAttemptedFor === fingerprint) return;
  resolutionAttemptedFor = fingerprint;
  const releaseLatch = () => {
    // A failed lookup must not pin the fallback identity for the rest of the
    // process. Released so the next capture tries again.
    if (resolutionAttemptedFor === fingerprint) resolutionAttemptedFor = "";
  };
  fetch(`${getBaseUrl().replace(/\/+$/, "")}/v1/ping/`, {
    method: "GET",
    headers: { Authorization: `Token ${apiKey}`, "Content-Type": "application/json" },
    signal: AbortSignal.timeout(5_000),
  })
    .then((response) => response.json())
    .then((data: any) => {
      if (!data?.user_email) return;
      writePluginAuth({ userEmail: data.user_email, keyFingerprint: fingerprint });
      const oldId = createHash("sha256").update(apiKey).digest("hex");
      const newId = createHash("sha256").update(data.user_email).digest("hex");
      for (const event of telemetry.queueForTesting()) {
        if (event.distinct_id === oldId) event.distinct_id = newId;
      }
    })
    .catch(() => {
      // The API-key hash remains a stable fallback, and the next capture retries.
      releaseLatch();
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
    let resolvedForThisKey = false;
    try {
      const auth = readPluginAuth();
      resolvedForThisKey =
        Boolean(auth.userEmail) && auth.keyFingerprint === keyFingerprint(context?.apiKey);
    } catch {
      // Resolve it below when possible.
    }
    if (context?.apiKey && !resolvedForThisKey) resolveEmail(context.apiKey);
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
