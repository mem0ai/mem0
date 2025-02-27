// @ts-nocheck
import type { PostHog } from "posthog-js";
import type { TelemetryClient } from "./telemetry.types";

let version = "1.0.20";

const MEM0_TELEMETRY = process.env.MEM0_TELEMETRY !== "false";
const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com";

// Browser-specific hash function using Web Crypto API
async function generateHash(input: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(input);
  const hashBuffer = await window.crypto.subtle.digest("SHA-256", msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

class BrowserTelemetry implements TelemetryClient {
  client: PostHog | null = null;

  constructor(projectApiKey: string, host: string) {
    if (MEM0_TELEMETRY) {
      this.initializeClient(projectApiKey, host);
    }
  }

  private async initializeClient(projectApiKey: string, host: string) {
    try {
      const posthog = await import("posthog-js").catch(() => null);
      if (posthog) {
        posthog.init(projectApiKey, { api_host: host });
        this.client = posthog;
      }
    } catch (error) {
      // Silently fail if posthog-js is not available
      this.client = null;
    }
  }

  async captureEvent(distinctId: string, eventName: string, properties = {}) {
    if (!this.client || !MEM0_TELEMETRY) return;

    const eventProperties = {
      client_source: "browser",
      client_version: getVersion(),
      browser: window.navigator.userAgent,
      ...properties,
    };

    try {
      this.client.capture(eventName, eventProperties);
    } catch (error) {
      // Silently fail if telemetry fails
    }
  }

  async shutdown() {
    // No shutdown needed for browser client
  }
}

function getVersion() {
  return version;
}

const telemetry = new BrowserTelemetry(POSTHOG_API_KEY, POSTHOG_HOST);

async function captureClientEvent(
  eventName: string,
  instance: any,
  additionalData = {},
) {
  const eventData = {
    function: `${instance.constructor.name}`,
    ...additionalData,
  };
  await telemetry.captureEvent(
    instance.telemetryId,
    `client.${eventName}`,
    eventData,
  );
}

export { telemetry, captureClientEvent, generateHash };
