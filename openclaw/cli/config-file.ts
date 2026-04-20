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
const NPM_PACKAGE = "@mem0/openclaw-mem0";

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

/**
 * Read the full ~/.openclaw/openclaw.json.
 *
 * Returns {} only when the file doesn't exist (first-time setup).
 * Throws on parse errors to prevent writes from destroying existing config.
 */
function readFullConfig(): Record<string, unknown> {
  if (!exists(OPENCLAW_CONFIG_FILE)) {
    return {};
  }

  const text = readText(OPENCLAW_CONFIG_FILE);

  // Handle empty or whitespace-only files as first-time setup
  if (!text.trim()) {
    return {};
  }

  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Config is not a JSON object");
    }
    return parsed;
  } catch (err) {
    // Fail closed: throw so writes don't proceed with empty config
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(
      `[openclaw-mem0] Failed to parse ${OPENCLAW_CONFIG_FILE}: ${msg}\n` +
        `Fix the JSON syntax error manually before running config commands.`,
    );
  }
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

  ensurePluginStructure(full);

  const cfg = full.plugins.entries[PLUGIN_ID].config;

  // Write all defined fields into the config section
  for (const [key, value] of Object.entries(auth)) {
    if (value !== undefined) cfg[key] = value;
  }

  writeFullConfig(full);
}

/**
 * Ensure the plugin has a valid install record and is in plugins.allow.
 *
 * OpenClaw's `plugins update` command requires a `plugins.installs.<id>`
 * record with `source: "npm"` and `spec` to know how to update. Without
 * this, `openclaw plugins update` prints "No install record" and skips.
 *
 * Similarly, if `plugins.allow` exists as an array, the plugin ID must
 * be in it or OpenClaw treats the plugin as untrusted.
 *
 * This is safe to call multiple times — it only writes missing fields.
 */
export function ensureInstallRecord(): void {
  try {
    const full = readFullConfig() as any;

    const entry = full?.plugins?.entries?.[PLUGIN_ID];
    const record = full?.plugins?.installs?.[PLUGIN_ID];
    const allow = full?.plugins?.allow;
    if (
      entry?.enabled === true &&
      record?.source &&
      record?.spec &&
      Array.isArray(allow) &&
      allow.includes(PLUGIN_ID)
    ) {
      return;
    }

    ensurePluginStructure(full);

    let changed = false;

    // Ensure install record exists for `openclaw plugins update` support
    if (!full.plugins.installs) full.plugins.installs = {};
    if (!full.plugins.installs[PLUGIN_ID]) {
      full.plugins.installs[PLUGIN_ID] = {
        source: "npm",
        spec: `${NPM_PACKAGE}@latest`,
        resolvedName: NPM_PACKAGE,
        installedAt: new Date().toISOString(),
      };
      changed = true;
    } else {
      const record = full.plugins.installs[PLUGIN_ID];
      if (!record.source) {
        record.source = "npm";
        changed = true;
      }
      if (!record.spec) {
        record.spec = `${NPM_PACKAGE}@latest`;
        changed = true;
      }
      if (!record.resolvedName) {
        record.resolvedName = NPM_PACKAGE;
        changed = true;
      }
    }

    if (!Array.isArray(full.plugins.allow)) {
      full.plugins.allow = [PLUGIN_ID];
      changed = true;
    } else if (!full.plugins.allow.includes(PLUGIN_ID)) {
      full.plugins.allow.push(PLUGIN_ID);
      changed = true;
    }

    if (changed) writeFullConfig(full);
  } catch {
    // Best-effort — don't break plugin loading if config is unreadable
  }
}

/** Ensure the nested plugin entry structure exists in the config object. */
function ensurePluginStructure(full: any): void {
  if (!full.plugins) full.plugins = {};
  if (!full.plugins.entries) full.plugins.entries = {};
  if (!full.plugins.entries[PLUGIN_ID]) {
    full.plugins.entries[PLUGIN_ID] = { enabled: true, config: {} };
  }
  if (!full.plugins.entries[PLUGIN_ID].config) {
    full.plugins.entries[PLUGIN_ID].config = {};
  }
}

export function writePluginConfigField(
  path: string[],
  value: unknown,
): void {
  const full = readFullConfig() as any;

  ensurePluginStructure(full);

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

/** Remove anonymousTelemetryId from config (after PostHog aliasing) */
export function clearAnonymousTelemetryId(): void {
  const full = readFullConfig() as any;
  const cfg = full?.plugins?.entries?.[PLUGIN_ID]?.config;
  if (cfg && "anonymousTelemetryId" in cfg) {
    delete cfg.anonymousTelemetryId;
    writeFullConfig(full);
  }
}
