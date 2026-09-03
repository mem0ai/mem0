import { randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import {
  createTelemetry,
  errorKind,
  isTelemetryEnabled,
} from "../../agent-plugin-core/typescript/src/telemetry.ts";

export { errorKind, isTelemetryEnabled };

const PLUGIN_VERSION = (() => {
  try {
    return JSON.parse(fs.readFileSync(new URL("../package.json", import.meta.url), "utf-8")).version;
  } catch {
    return "unknown";
  }
})();

export interface TelemetryIdentity {
  telemetryId?: string;
}

let cachedAnonymousId: string | undefined;
let identified = false;
let currentDistinctId = "";

function identityPath(): string {
  return path.join(os.homedir(), ".mem0", "deepseek-plugin-telemetry.json");
}

function anonymousId(): string {
  if (cachedAnonymousId) return cachedAnonymousId;
  try {
    const stored = JSON.parse(fs.readFileSync(identityPath(), "utf-8"));
    if (typeof stored.anonymousId === "string" && stored.anonymousId) {
      return (cachedAnonymousId = stored.anonymousId);
    }
  } catch {
    // First run or unreadable identity file.
  }
  const created = `deepseek-anon-${randomUUID().replace(/-/g, "")}`;
  try {
    fs.mkdirSync(path.dirname(identityPath()), { recursive: true });
    fs.writeFileSync(identityPath(), JSON.stringify({ anonymousId: created }), "utf-8");
  } catch {
    // An unwritable home directory must not break the plugin.
  }
  return (cachedAnonymousId = created);
}

function previousAnonymousId(distinctId: string): string | undefined {
  if (identified || distinctId.startsWith("deepseek-anon-")) return undefined;
  identified = true;
  try {
    const stored = JSON.parse(fs.readFileSync(identityPath(), "utf-8")).anonymousId;
    fs.unlinkSync(identityPath());
    cachedAnonymousId = undefined;
    return typeof stored === "string" && stored ? stored : undefined;
  } catch {
    return undefined;
  }
}

const telemetry = createTelemetry({
  host: "deepseek",
  source: "DEEPSEEK_HARNESS",
  version: PLUGIN_VERSION,
  distinctId: () => currentDistinctId,
});

export function captureEvent(
  event: string,
  properties: Record<string, unknown>,
  client: TelemetryIdentity,
): void {
  currentDistinctId = client.telemetryId || anonymousId();
  const anonymous = previousAnonymousId(currentDistinctId);
  if (anonymous) telemetry.capture("$identify", { $anon_distinct_id: anonymous });
  telemetry.capture(event, properties);
}

export function flushEvents(): void {
  void telemetry.flush();
}

export function _queueForTesting(): Record<string, unknown>[] {
  return telemetry.queueForTesting();
}

export function _resetForTesting(): void {
  telemetry.resetForTesting();
  cachedAnonymousId = undefined;
  currentDistinctId = "";
  identified = false;
}
