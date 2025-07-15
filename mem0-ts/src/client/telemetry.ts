// @ts-nocheck
import type { TelemetryClient, TelemetryOptions } from "./telemetry.types";

let version = "2.1.36";

// Safely check for process.env in different environments
let MEM0_TELEMETRY = true;
try {
  MEM0_TELEMETRY = process?.env?.MEM0_TELEMETRY === "false" ? false : true;
} catch (error) {}
const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

// Simple hash function using random strings
function generateHash(input: string): string {
  const randomStr =
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15);
  return randomStr;
}

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

export { telemetry, captureClientEvent, generateHash };
