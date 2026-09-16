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
const MAX_HEADER_CHARS = 200;

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
  existing.push(`mem0-pi-agent/${PLUGIN_VERSION}`);
  headers["X-Mem0-Client"] = existing
    .slice(0, MAX_STACK_ENTRIES)
    .join(", ")
    .slice(0, MAX_HEADER_CHARS);
}
