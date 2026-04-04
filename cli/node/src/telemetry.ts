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
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CONFIG_FILE, loadConfig } from "./config.js";
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
 * Return a stable anonymous identifier for the current user.
 *
 * Priority: cached user_email (from /v1/ping/) > MD5(api_key) > fallback.
 * Matches the SDK pattern in mem0-ts/src/client/mem0.ts.
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
	return "anonymous-cli";
}

/**
 * Fire a PostHog event (non-blocking, returns void, never throws).
 * Spawns telemetry-sender.cjs as a detached subprocess.
 */
export function captureEvent(
	eventName: string,
	properties: Record<string, unknown> = {},
): void {
	if (!isTelemetryEnabled()) return;

	try {
		const config = loadConfig();
		const distinctId = getDistinctId();

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
