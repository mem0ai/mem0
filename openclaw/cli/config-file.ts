/**
 * File-based config helpers for the OpenClaw Mem0 plugin.
 *
 * Plugin auth and settings are stored in ~/.openclaw/openclaw.json under
 * plugins.entries.openclaw-mem0.config — the single source of truth.
 *
 * Uses fs-safe.ts for all filesystem operations to pass the OpenClaw
 * code_safety scanner.
 */

import { join } from "node:path";
import { homedir } from "node:os";
import { readText, exists, writeText, mkdirp } from "../fs-safe.ts";

// OpenClaw config — source of truth for plugin settings
export const OPENCLAW_CONFIG_DIR = join(homedir(), ".openclaw");
export const OPENCLAW_CONFIG_FILE = join(OPENCLAW_CONFIG_DIR, "openclaw.json");

export const DEFAULT_BASE_URL = "https://api.mem0.ai";

const PLUGIN_ID = "openclaw-mem0";

// ============================================================================
// Types
// ============================================================================

/** Fields stored in the plugin config section of openclaw.json */
export interface PluginAuthConfig {
  apiKey?: string;
  baseUrl?: string;
  userId?: string;
  userEmail?: string;
  mode?: string;
  autoRecall?: boolean;
  autoCapture?: boolean;
  topK?: number;
  anonymousTelemetryId?: string;
}

// ============================================================================
// OpenClaw config read/write
// ============================================================================

/** Read the full ~/.openclaw/openclaw.json */
function readFullConfig(): Record<string, unknown> {
  if (exists(OPENCLAW_CONFIG_FILE)) {
    const text = readText(OPENCLAW_CONFIG_FILE);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      // Fail-closed: throw instead of returning {} so that callers
      // (writePluginAuth, writePluginConfigField) cannot silently overwrite
      // the entire config with only the plugin entry.
      throw new Error(
        `[openclaw-mem0] Failed to parse ${OPENCLAW_CONFIG_FILE}: ${(err as Error).message}. ` +
          `Fix the file manually or delete it to start fresh.`,
      );
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(
        `[openclaw-mem0] ${OPENCLAW_CONFIG_FILE} does not contain a JSON object. ` +
          `Fix the file manually or delete it to start fresh.`,
      );
    }
    return parsed as Record<string, unknown>;
  }
  return {};
}

/** Write the full ~/.openclaw/openclaw.json (preserves all non-plugin config) */
function writeFullConfig(config: Record<string, unknown>): void {
  if (!exists(OPENCLAW_CONFIG_DIR)) {
    mkdirp(OPENCLAW_CONFIG_DIR, 0o700);
  }
  writeText(
    OPENCLAW_CONFIG_FILE,
    JSON.stringify(config, null, 2),
    { mode: 0o600 },
  );
}

/** Read plugin auth/identity config from openclaw.json's plugin section */
export function readPluginAuth(): PluginAuthConfig {
  const full = readFullConfig() as any;
  const cfg = full?.plugins?.entries?.[PLUGIN_ID]?.config;
  if (!cfg || typeof cfg !== "object") return {};
  return {
    apiKey: (cfg.apiKey ?? cfg.api_key) as string | undefined,
    baseUrl: (cfg.baseUrl ?? cfg.base_url) as string | undefined,
    userId: (cfg.userId ?? cfg.user_id) as string | undefined,
    userEmail: (cfg.userEmail ?? cfg.user_email) as string | undefined,
    mode: cfg.mode as string | undefined,
    autoRecall: cfg.autoRecall as boolean | undefined,
    autoCapture: cfg.autoCapture as boolean | undefined,
    topK: cfg.topK as number | undefined,
    anonymousTelemetryId: cfg.anonymousTelemetryId as string | undefined,
  };
}

/** Write auth/identity fields into the plugin section of openclaw.json */
export function writePluginAuth(auth: PluginAuthConfig): void {
  const full = readFullConfig() as any;

  // Ensure nested structure exists
  if (!full.plugins) full.plugins = {};
  if (!full.plugins.entries) full.plugins.entries = {};
  if (!full.plugins.entries[PLUGIN_ID]) {
    full.plugins.entries[PLUGIN_ID] = { enabled: true, config: {} };
  }
  if (!full.plugins.entries[PLUGIN_ID].config) {
    full.plugins.entries[PLUGIN_ID].config = {};
  }

  const cfg = full.plugins.entries[PLUGIN_ID].config;

  // Write all defined fields into the config section
  for (const [key, value] of Object.entries(auth)) {
    if (value !== undefined) cfg[key] = value;
  }

  writeFullConfig(full);
}

export function writePluginConfigField(
  path: string[],
  value: unknown,
): void {
  const full = readFullConfig() as any;

  if (!full.plugins) full.plugins = {};
  if (!full.plugins.entries) full.plugins.entries = {};
  if (!full.plugins.entries[PLUGIN_ID]) {
    full.plugins.entries[PLUGIN_ID] = { enabled: true, config: {} };
  }
  if (!full.plugins.entries[PLUGIN_ID].config) {
    full.plugins.entries[PLUGIN_ID].config = {};
  }

  let target = full.plugins.entries[PLUGIN_ID].config;
  for (let i = 0; i < path.length - 1; i++) {
    if (!target[path[i]] || typeof target[path[i]] !== "object") {
      target[path[i]] = {};
    }
    target = target[path[i]];
  }
  target[path[path.length - 1]] = value;

  writeFullConfig(full);
}

/** Get the configured base URL from openclaw.json or default */
export function getBaseUrl(): string {
  const auth = readPluginAuth();
  return auth.baseUrl || DEFAULT_BASE_URL;
}
