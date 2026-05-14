/**
 * Configuration management for mem0 CLI.
 *
 * Config precedence (highest to lowest):
 * 1. CLI flags (--api-key, --base-url, etc.)
 * 2. Environment variables (MEM0_API_KEY, etc.)
 * 3. Config file (~/.mem0/config.json)
 * 4. Defaults
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const CONFIG_DIR = path.join(os.homedir(), ".mem0");
export const CONFIG_FILE = path.join(CONFIG_DIR, "config.json");
export const DEFAULT_BASE_URL = "https://api.mem0.ai";
export const CONFIG_VERSION = 1;

export interface PlatformConfig {
	apiKey: string;
	baseUrl: string;
	userEmail: string;
	// Agent Mode (unclaimed-shadow signup)
	agentMode: boolean; // true while the key is an unclaimed agent-mode key
	createdVia: string; // "agent_mode" | "email" | "api_key" | "existing_key"
	agentCaller: string; // canonical agent name when createdVia === "agent_mode" (e.g. "claude-code")
	claimedAt: string; // ISO timestamp once the agent has been claimed
	defaultUserId: string; // `user_<slug>` returned by bootstrap; auto-default scope
}

export interface DefaultsConfig {
	userId: string;
	agentId: string;
	appId: string;
	runId: string;
}

export interface TelemetryConfig {
	anonymousId: string;
}

export interface Mem0Config {
	version: number;
	defaults: DefaultsConfig;
	platform: PlatformConfig;
	telemetry: TelemetryConfig;
}

export function createDefaultConfig(): Mem0Config {
	return {
		version: CONFIG_VERSION,
		defaults: {
			userId: "",
			agentId: "",
			appId: "",
			runId: "",
		},
		platform: {
			apiKey: "",
			baseUrl: DEFAULT_BASE_URL,
			userEmail: "",
			agentMode: false,
			createdVia: "",
			agentCaller: "",
			claimedAt: "",
			defaultUserId: "",
		},
		telemetry: {
			anonymousId: "",
		},
	};
}

export function ensureConfigDir(): string {
	fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
	return CONFIG_DIR;
}

export function loadConfig(): Mem0Config {
	const config = createDefaultConfig();

	if (fs.existsSync(CONFIG_FILE)) {
		const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
		const data = JSON.parse(raw);

		config.version = data.version ?? CONFIG_VERSION;

		const plat = data.platform ?? {};
		config.platform.apiKey = plat.api_key ?? "";
		config.platform.baseUrl = plat.base_url ?? DEFAULT_BASE_URL;
		config.platform.userEmail = plat.user_email ?? "";
		config.platform.agentMode = Boolean(plat.agent_mode ?? false);
		config.platform.createdVia = plat.created_via ?? "";
		config.platform.agentCaller = plat.agent_caller ?? "";
		config.platform.claimedAt = plat.claimed_at ?? "";
		config.platform.defaultUserId = plat.default_user_id ?? "";

		const defaults = data.defaults ?? {};
		config.defaults.userId = defaults.user_id ?? "";
		config.defaults.agentId = defaults.agent_id ?? "";
		config.defaults.appId = defaults.app_id ?? "";
		config.defaults.runId = defaults.run_id ?? "";
		const telemetry = data.telemetry ?? {};
		config.telemetry.anonymousId = telemetry.anonymous_id ?? "";
	}

	// Environment variable overrides
	if (process.env.MEM0_API_KEY)
		config.platform.apiKey = process.env.MEM0_API_KEY;
	if (process.env.MEM0_BASE_URL)
		config.platform.baseUrl = process.env.MEM0_BASE_URL;
	if (process.env.MEM0_USER_ID)
		config.defaults.userId = process.env.MEM0_USER_ID;
	if (process.env.MEM0_AGENT_ID)
		config.defaults.agentId = process.env.MEM0_AGENT_ID;
	if (process.env.MEM0_APP_ID) config.defaults.appId = process.env.MEM0_APP_ID;
	if (process.env.MEM0_RUN_ID) config.defaults.runId = process.env.MEM0_RUN_ID;
	return config;
}

export function saveConfig(config: Mem0Config): void {
	ensureConfigDir();

	const data = {
		version: config.version,
		defaults: {
			user_id: config.defaults.userId,
			agent_id: config.defaults.agentId,
			app_id: config.defaults.appId,
			run_id: config.defaults.runId,
		},
		platform: {
			api_key: config.platform.apiKey,
			base_url: config.platform.baseUrl,
			user_email: config.platform.userEmail,
			agent_mode: config.platform.agentMode,
			created_via: config.platform.createdVia,
			agent_caller: config.platform.agentCaller,
			claimed_at: config.platform.claimedAt,
			default_user_id: config.platform.defaultUserId,
		},
		telemetry: {
			anonymous_id: config.telemetry.anonymousId,
		},
	};

	fs.writeFileSync(CONFIG_FILE, JSON.stringify(data, null, 2));
	fs.chmodSync(CONFIG_FILE, 0o600);

	// Propagate api_key to ecosystem touchpoints (Claude plugin env injection,
	// shell rc exports). Idempotent — updates only EXISTING entries; never
	// creates new ones. Best-effort: errors swallowed so config.json is
	// always authoritative, never blocked by plugin-state issues.
	if (config.platform.apiKey) {
		try {
			// eslint-disable-next-line @typescript-eslint/no-require-imports
			const { syncApiKey } = require("./plugin-sync.js");
			syncApiKey(config.platform.apiKey);
		} catch {
			/* swallow */
		}
	}
}

export function redactKey(key: string): string {
	if (!key) return "(not set)";
	if (key.length <= 8) return `${key.slice(0, 2)}***`;
	return `${key.slice(0, 4)}...${key.slice(-4)}`;
}

/** Key map from dotted config path to the config object fields. */
const KEY_MAP: Record<string, [keyof Mem0Config, string]> = {
	"platform.api_key": ["platform", "apiKey"],
	"platform.base_url": ["platform", "baseUrl"],
	"platform.user_email": ["platform", "userEmail"],
	"defaults.user_id": ["defaults", "userId"],
	"defaults.agent_id": ["defaults", "agentId"],
	"defaults.app_id": ["defaults", "appId"],
	"defaults.run_id": ["defaults", "runId"],
	// Short-form aliases
	api_key: ["platform", "apiKey"],
	base_url: ["platform", "baseUrl"],
	user_email: ["platform", "userEmail"],
	user_id: ["defaults", "userId"],
	agent_id: ["defaults", "agentId"],
	app_id: ["defaults", "appId"],
	run_id: ["defaults", "runId"],
};

export function getNestedValue(config: Mem0Config, dottedKey: string): unknown {
	const mapping = KEY_MAP[dottedKey];
	if (!mapping) return undefined;
	const [section, field] = mapping;
	return (config[section] as unknown as Record<string, unknown>)[field];
}

export function setNestedValue(
	config: Mem0Config,
	dottedKey: string,
	value: string,
): boolean {
	const mapping = KEY_MAP[dottedKey];
	if (!mapping) return false;
	const [section, field] = mapping;
	const obj = config[section] as unknown as Record<string, unknown>;

	const current = obj[field];
	if (typeof current === "boolean") {
		obj[field] = ["true", "1", "yes"].includes(value.toLowerCase());
	} else if (typeof current === "number") {
		obj[field] = Number.parseInt(value, 10);
	} else {
		obj[field] = value;
	}
	return true;
}
