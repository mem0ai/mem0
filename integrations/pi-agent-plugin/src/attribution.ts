import type MemoryClient from "mem0ai";
import * as fs from "node:fs";

/** Surface identity for this plugin, as the platform's EventSource knows it. */
export const PLATFORM_SOURCE = "PI_AGENT";

/** Host app the plugin runs inside. Allowlisted server-side. */
export const PLATFORM_APPLICATION = "pi";

const PLUGIN_VERSION = (() => {
  try {
    return JSON.parse(
      fs.readFileSync(new URL("../package.json", import.meta.url), "utf-8"),
    ).version as string;
  } catch {
    return "unknown";
  }
})();

const MAX_STACK_ENTRIES = 4;
const MAX_STACK_CHARS = 200;

/**
 * Append our own entry and bound the result, dropping WHOLE entries.
 *
 * Neither cap cuts characters: slicing the joined string severs an identifier
 * and leaves a fragment the platform parses as a real client name. And the
 * reserved slot is ours, since it is the only entry this layer can vouch for.
 */
function boundedStack(callerEntries: string[], own: string): string {
  const kept: string[] = [];
  let budget = MAX_STACK_CHARS - own.length;
  for (const entry of callerEntries.slice(0, MAX_STACK_ENTRIES - 1)) {
    const cost = entry.length + ", ".length;
    if (cost > budget) break;
    budget -= cost;
    kept.push(entry);
  }
  return [...kept, own].join(", ");
}

/**
 * Stamp surface identity onto the shared client, once, at construction.
 *
 * Tagging individual call sites was not enough: automatic recall, capture, the
 * memory tools and deletion all go through this same client, so everything
 * except the explicit slash commands reached the platform as generic SDK
 * traffic. Every request method in the SDK sends `this.headers`, so setting
 * them here covers all of them.
 *
 * X-Mem0-Source and X-Application are set-once, so a wrapper that already named
 * a surface keeps it. X-Mem0-Client is append-only, so the platform sees the
 * whole chain rather than only the last speaker.
 */
export function applySurfaceHeaders(client: MemoryClient): void {
  const headers = client.headers as Record<string, string>;
  if (!headers["X-Mem0-Source"]?.trim()) headers["X-Mem0-Source"] = PLATFORM_SOURCE;
  if (!headers["X-Application"]?.trim()) headers["X-Application"] = PLATFORM_APPLICATION;

  const existing = (headers["X-Mem0-Client"] ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  headers["X-Mem0-Client"] = boundedStack(existing, `mem0-pi-agent/${PLUGIN_VERSION}`);
}
