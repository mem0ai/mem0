import { createHash, randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

import { createTelemetry } from "../../agent-plugins/core/typescript/src/telemetry.ts";
import { CONFIG_DIR } from "./config/index.ts";

const PLUGIN_VERSION = (() => {
  try {
    return JSON.parse(fs.readFileSync(new URL("../package.json", import.meta.url), "utf-8")).version;
  } catch {
    return "unknown";
  }
})();
const TELEMETRY_ID_PATH = path.join(CONFIG_DIR, "mem0-telemetry-id.json");

let cachedAnonymousId: string | undefined;
let currentDistinctId = "";
let identified = false;

function anonymousId(): string {
  if (cachedAnonymousId) return cachedAnonymousId;
  try {
    const stored = JSON.parse(fs.readFileSync(TELEMETRY_ID_PATH, "utf-8")).anonymousId;
    if (typeof stored === "string" && stored) return (cachedAnonymousId = stored);
  } catch {
    // First run or unreadable identity file.
  }
  const created = `pi-mem0-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
    fs.writeFileSync(TELEMETRY_ID_PATH, JSON.stringify({ anonymousId: created }), "utf-8");
  } catch {
    // An unwritable config directory must not break the plugin.
  }
  return (cachedAnonymousId = created);
}

function distinctId(apiKey?: string): string {
  return apiKey ? createHash("sha256").update(apiKey).digest("hex") : anonymousId();
}

function previousAnonymousId(id: string): string | undefined {
  if (identified || id.startsWith("pi-mem0-anon-")) return undefined;
  identified = true;
  try {
    const stored = JSON.parse(fs.readFileSync(TELEMETRY_ID_PATH, "utf-8")).anonymousId;
    fs.unlinkSync(TELEMETRY_ID_PATH);
    cachedAnonymousId = undefined;
    return typeof stored === "string" && stored ? stored : undefined;
  } catch {
    return undefined;
  }
}

const telemetry = createTelemetry({
  host: "pi",
  source: "PI_AGENT_PLUGIN",
  version: PLUGIN_VERSION,
  distinctId: () => currentDistinctId,
});

export function captureEvent(
  eventName: string,
  properties: Record<string, unknown> = {},
  context?: { apiKey?: string },
): void {
  currentDistinctId = distinctId(context?.apiKey);
  const anonymous = previousAnonymousId(currentDistinctId);
  if (anonymous) telemetry.capture("$identify", { $anon_distinct_id: anonymous });
  telemetry.capture(eventName, properties);
}

export function captureToolEvent(
  action: string,
  properties: Record<string, unknown> = {},
  context?: { apiKey?: string },
): void {
  captureEvent("pi.tool.mem0_memory", { action, ...properties }, context);
}

export function captureCommandEvent(
  command: string,
  properties: Record<string, unknown> = {},
  context?: { apiKey?: string },
): void {
  captureEvent(`pi.command.${command}`, properties, context);
}

export function _getEventQueue(): Record<string, unknown>[] {
  return telemetry.queueForTesting();
}

export function _resetForTesting(): void {
  telemetry.resetForTesting();
  cachedAnonymousId = undefined;
  currentDistinctId = "";
  identified = false;
}
