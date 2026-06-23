/**
 * Test shim for openclaw/plugin-sdk/plugin-entry.
 * At runtime this is resolved from the OpenClaw gateway.
 */
export function definePluginEntry<T>(entry: T): T {
  return entry;
}
