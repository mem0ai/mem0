/**
 * CLI telemetry — anonymous usage tracking via PostHog.
 *
 * Sends fire-and-forget events by spawning a detached child process
 * (telemetry-sender.cjs). The parent CLI process exits immediately;
 * the child handles email resolution, caching, and the HTTP POST.
 *
 * Disable with: MEM0_TELEMETRY=false
 */

import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CONFIG_FILE, loadConfig, saveConfig } from "./config.js";
import { CLI_VERSION } from "./version.js";

const POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX";
const POSTHOG_HOST = "https://us.i.posthog.com/i/v0/e/";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SENDER_SCRIPT = path.join(__dirname, "..", "telemetry-sender.cjs");

function isTelemetryEnabled(): boolean {
	try {
		return process.env.MEM0_TELEMETRY !== "false";
	} catch {
		return true;
	}
}

/**
 * Return a persistent per-machine anonymous ID, generating one if needed.
 *
 * Stored in ~/.mem0/config.json under `telemetry.anonymous_id` so that
 * repeat runs on the same machine share one PostHog identity instead of
 * collapsing into a single shared fallback string.
 */
function getOrCreateAnonymousId(): string {
	const config = loadConfig();
	if (config.telemetry.anonymousId) {
		return config.telemetry.anonymousId;
	}

	const newId = `cli-anon-${randomUUID().replace(/-/g, "")}`;
	config.telemetry.anonymousId = newId;
	try {
		saveConfig(config);
	} catch {
		/* ignore persistence failure — still return the generated ID */
	}
	return newId;
}

/**
 * Return a stable anonymous identifier for the current user.
 *
 * Priority: cached user_email (from /v1/ping/) > MD5(api_key) >
 * persistent per-machine anonymous ID.
 */
function getDistinctId(): string {
	try {
		const config = loadConfig();
		if (config.platform.userEmail) {
			return config.platform.userEmail;
		}
		if (config.platform.apiKey) {
			return createHash("md5").update(config.platform.apiKey).digest("hex");
		}
	} catch {
		/* ignore */
	}
	try {
		return getOrCreateAnonymousId();
	} catch {
		return `cli-anon-${randomUUID().replace(/-/g, "")}`;
	}
}

/**
 * Fire a PostHog event (non-blocking, returns void, never throws).
 * Spawns telemetry-sender.cjs as a detached subprocess.
 *
 * When `preResolvedEmail` is provided (e.g. from an upfront ping
 * validation), it is used directly as the PostHog distinct ID and the
 * subprocess skips its own `/v1/ping/` call.
 */
export function captureEvent(
	eventName: string,
	properties: Record<string, unknown> = {},
	preResolvedEmail?: string,
): void {
	if (!isTelemetryEnabled()) return;

	try {
		const config = loadConfig();
		const distinctId = preResolvedEmail || getDistinctId();

		// Detect anonymous → identified transition. If a stored anonymous_id
		// exists and we just resolved to a real identity, fire a one-shot
		// $identify event so PostHog stitches the pre-signup history onto
		// the authenticated profile. Clear the stored id so we don't re-alias.
		let anonIdToAlias: string | null = null;
		if (
			distinctId &&
			!distinctId.startsWith("cli-anon-") &&
			config.telemetry.anonymousId
		) {
			anonIdToAlias = config.telemetry.anonymousId;
			config.telemetry.anonymousId = "";
			try {
				saveConfig(config);
			} catch {
				/* ignore — alias may double-fire next run, harmless */
			}
		}

		const payload = {
			api_key: POSTHOG_API_KEY,
			distinct_id: distinctId,
			event: eventName,
			properties: {
				source: "CLI",
				language: "node",
				cli_version: CLI_VERSION,
				node_version: process.version,
				os: process.platform,
				...properties,
				$process_person_profile: false,
				$lib: "posthog-node",
			},
		};

		const context = {
			payload,
			posthogHost: POSTHOG_HOST,
			needsEmail: !distinctId || !distinctId.includes("@"),
			mem0ApiKey: config.platform.apiKey || "",
			mem0BaseUrl: config.platform.baseUrl || "https://api.mem0.ai",
			configPath: CONFIG_FILE,
			anonDistinctIdToAlias: anonIdToAlias,
		};

		const child = spawn(
			process.execPath,
			[SENDER_SCRIPT, JSON.stringify(context)],
			{ detached: true, stdio: "ignore" },
		);
		child.unref();
	} catch {
		/* silently swallow */
	}
}
