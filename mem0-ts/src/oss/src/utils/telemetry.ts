import type {
  TelemetryClient,
  TelemetryInstance,
  TelemetryEventData,
} from "./telemetry.types";

let version = "2.1.34";

// Safely check for process.env in different environments
let MEM0_TELEMETRY = true;
try {
  MEM0_TELEMETRY = process?.env?.MEM0_TELEMETRY === "false" ? false : true;
} catch (error) {}
const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

// Sampling: hot-path events (add/search/get/...) are sampled at this rate to
// keep PostHog volume bounded. Lifecycle events ('init', 'reset') always fire
// at 100% so the active-install heartbeat stays exact. The default (10%) sits
// in the middle of PostHog's recommended 5–20% range; users can override via
// MEM0_TELEMETRY_SAMPLE_RATE. Mirrors mem0/memory/telemetry.py.
const DEFAULT_SAMPLE_RATE = 0.1;
const MEM0_TELEMETRY_SAMPLE_RATE: number = ((): number => {
  try {
    const raw = process?.env?.MEM0_TELEMETRY_SAMPLE_RATE;
    if (raw !== undefined) {
      const parsed = Number(raw);
      if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 1) {
        return parsed;
      }
    }
  } catch {}
  return DEFAULT_SAMPLE_RATE;
})();

// Method names (unprefixed) that bypass sampling. Keep in sync with the
// _captureEvent call sites in memory/index.ts. The Python equivalent uses
// prefixed names (mem0.init, mem0.reset) — same set, different convention.
// Typed as ReadonlySet to prevent downstream consumers from mutating the set
// (the Python equivalent uses frozenset for the same reason).
const LIFECYCLE_EVENTS: ReadonlySet<string> = new Set(["init", "reset"]);

class UnifiedTelemetry implements TelemetryClient {
  private apiKey: string;
  private host: string;

  constructor(projectApiKey: string, host: string) {
    this.apiKey = projectApiKey;
    this.host = host;
  }

  async captureEvent(distinctId: string, eventName: string, properties = {}) {
    if (!MEM0_TELEMETRY) return;

    const eventProperties = {
      client_version: version,
      timestamp: new Date().toISOString(),
      ...properties,
      $process_person_profile:
        distinctId === "anonymous" || distinctId === "anonymous-supabase"
          ? false
          : true,
      $lib: "posthog-node",
    };

    const payload = {
      api_key: this.apiKey,
      distinct_id: distinctId,
      event: eventName,
      properties: eventProperties,
    };

    try {
      const response = await fetch(this.host, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        console.error("Telemetry event capture failed:", await response.text());
      }
    } catch (error) {
      console.error("Telemetry event capture failed:", error);
    }
  }

  async shutdown() {
    // No shutdown needed for direct API calls
  }
}

const telemetry = new UnifiedTelemetry(POSTHOG_API_KEY, POSTHOG_HOST);

async function captureClientEvent(
  eventName: string,
  instance: TelemetryInstance,
  additionalData: Record<string, any> = {},
) {
  if (!instance.telemetryId) {
    console.warn("No telemetry ID found for instance");
    return;
  }

  // Sample hot-path events; lifecycle events always fire (active-install heartbeat).
  // Standard observability-library gate: Math.random() ∈ [0, 1), so >= rate means
  // rate=0 always drops and rate=1 always keeps. Using > would let random=0 slip
  // through at rate=0.
  const isLifecycle = LIFECYCLE_EVENTS.has(eventName);
  if (!isLifecycle && Math.random() >= MEM0_TELEMETRY_SAMPLE_RATE) {
    return;
  }

  const eventData: TelemetryEventData = {
    function: `${instance.constructor.name}`,
    method: eventName,
    api_host: instance.host,
    timestamp: new Date().toISOString(),
    client_version: version,
    client_source: "nodejs",
    ...additionalData,
    // sample_rate set AFTER the spread so callers can never override it
    sample_rate: isLifecycle ? 1.0 : MEM0_TELEMETRY_SAMPLE_RATE,
  };

  await telemetry.captureEvent(
    instance.telemetryId,
    `mem0.${eventName}`,
    eventData,
  );
}

export {
  telemetry,
  captureClientEvent,
  // Exported for tests only.
  MEM0_TELEMETRY_SAMPLE_RATE,
  LIFECYCLE_EVENTS,
};
