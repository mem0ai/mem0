// @ts-nocheck
import type { TelemetryClient, TelemetryOptions } from "./telemetry.types";

// __MEM0_SDK_VERSION__ is inlined by tsup/esbuild's `define` at build time from
// package.json. In unbundled environments (ts-jest, jest globalSetup) the
// identifier is not defined, so guard with typeof to fall back safely.
let version =
  typeof __MEM0_SDK_VERSION__ !== "undefined" ? __MEM0_SDK_VERSION__ : "dev";

// Safely check for process.env in different environments
let MEM0_TELEMETRY = true;
try {
  MEM0_TELEMETRY = process?.env?.MEM0_TELEMETRY === "false" ? false : true;
} catch (error) {}
const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

// Deterministic, dependency-free hash (FNV-1a, 32-bit) over the input.
//
// This is used as the telemetry distinct_id before/without a successful ping.
// It used to ignore `input` and return Math.random(), which minted a brand new
// id per client instance and orphaned every event from a client that could not
// ping. Deterministic means one id per API key, in every runtime, with no I/O
// and no platform APIs (works in Node, browsers, edge runtimes, Deno, Bun).
//
// Not cryptographic and not reversible into the key: 32 bits of a secret is not
// a secret, and only the digest is ever transmitted.
function generateHash(input: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return `anon-${hash.toString(36)}`;
}

class UnifiedTelemetry implements TelemetryClient {
  private apiKey: string;
  private host: string;

  constructor(projectApiKey: string, host: string) {
    this.apiKey = projectApiKey;
    this.host = host;
  }

  async captureEvent(
    distinctId: string,
    eventName: string,
    properties = {},
  ): Promise<boolean> {
    if (!MEM0_TELEMETRY) return false;

    const eventProperties = {
      client_version: version,
      timestamp: new Date().toISOString(),
      ...properties,
      $process_person_profile: false,
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
        return false;
      }
      return true;
    } catch (error) {
      console.error("Telemetry event capture failed:", error);
      return false;
    }
  }

  async captureIdentify(anonId: string, email: string): Promise<boolean> {
    if (!MEM0_TELEMETRY) return false;
    if (!anonId || !email || anonId === email) return false;

    const payload = {
      api_key: this.apiKey,
      distinct_id: email,
      event: "$identify",
      properties: {
        $anon_distinct_id: anonId,
        client_source: "typescript",
        $lib: "posthog-node",
      },
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
        console.error(
          "Telemetry identify capture failed:",
          await response.text(),
        );
        return false;
      }
      return true;
    } catch (error) {
      console.error("Telemetry identify capture failed:", error);
      return false;
    }
  }

  async shutdown() {
    // No shutdown needed for direct API calls
  }
}

function isTelemetryEnabled(): boolean {
  return MEM0_TELEMETRY;
}

const telemetry = new UnifiedTelemetry(POSTHOG_API_KEY, POSTHOG_HOST);

async function captureClientEvent(
  eventName: string,
  instance: any,
  additionalData = {},
) {
  if (!instance.telemetryId) {
    console.warn("No telemetry ID found for instance");
    return;
  }

  const eventData = {
    function: `${instance.constructor.name}`,
    method: eventName,
    api_host: instance.host,
    timestamp: new Date().toISOString(),
    client_version: version,
    keys: additionalData?.keys || [],
    ...additionalData,
  };

  await telemetry.captureEvent(
    instance.telemetryId,
    `client.${eventName}`,
    eventData,
  );
}

export { telemetry, captureClientEvent, generateHash, isTelemetryEnabled };
