// @ts-nocheck
import type { TelemetryClient } from "./telemetry.types";

let version = "1.0.20";

const MEM0_TELEMETRY = process.env.MEM0_TELEMETRY !== "false";
const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com";

// Node-specific hash function using crypto module
function generateHash(input: string): string {
  const crypto = require("crypto");
  return crypto.createHash("sha256").update(input).digest("hex");
}

class NodeTelemetry implements TelemetryClient {
  client: any = null;

  constructor(projectApiKey: string, host: string) {
    if (MEM0_TELEMETRY) {
      this.initializeClient(projectApiKey, host);
    }
  }

  private async initializeClient(projectApiKey: string, host: string) {
    try {
      const { PostHog } = await import("posthog-node").catch(() => ({
        PostHog: null,
      }));
      if (PostHog) {
        this.client = new PostHog(projectApiKey, { host, flushAt: 1 });
      }
    } catch (error) {
      // Silently fail if posthog-node is not available
      this.client = null;
    }
  }

  async captureEvent(distinctId: string, eventName: string, properties = {}) {
    if (!this.client || !MEM0_TELEMETRY) return;

    const eventProperties = {
      client_source: "nodejs",
      client_version: getVersion(),
      ...this.getEnvironmentInfo(),
      ...properties,
    };

    try {
      this.client.capture({
        distinctId,
        event: eventName,
        properties: eventProperties,
      });
    } catch (error) {
      // Silently fail if telemetry fails
    }
  }

  private getEnvironmentInfo() {
    try {
      const os = require("os");
      return {
        node_version: process.version,
        os: process.platform,
        os_version: os.release(),
        os_arch: os.arch(),
      };
    } catch (error) {
      return {};
    }
  }

  async shutdown() {
    if (this.client) {
      try {
        return this.client.shutdown();
      } catch (error) {
        // Silently fail shutdown
      }
    }
  }
}

function getVersion() {
  return version;
}

const telemetry = new NodeTelemetry(POSTHOG_API_KEY, POSTHOG_HOST);

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
