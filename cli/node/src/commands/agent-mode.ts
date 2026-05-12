/**
 * Agent Mode commands — bootstrap (unattended signup) and claim (human upgrade).
 */

import { randomBytes } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import { colors, printError, printInfo, printSuccess } from "../branding.js";
import { type Mem0Config, saveConfig } from "../config.js";

const { dim } = colors;

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 600_000; // 10 minutes — fits within backend's 15-minute CLILoginRequest expiry.

const SOURCE_HEADERS = {
	"X-Mem0-Source": "cli",
	"X-Mem0-Client-Language": "node",
} as const;

export interface BootstrapEnvelope {
	api_key: string;
	default_user_id: string;
	org_id: string;
	project_id: string;
	mcp_url?: string;
	smoke_test_url?: string;
	claim_command?: string;
}

export async function bootstrapViaBackend(
	config: Mem0Config,
	{ source }: { source?: string | null } = {},
): Promise<void> {
	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(/\/+$/, "");
	const body: Record<string, unknown> = {};
	if (source) body.source = source;

	let resp: Response;
	try {
		resp = await fetch(`${baseUrl}/api/v1/auth/agent_mode/`, {
			method: "POST",
			headers: {
				...SOURCE_HEADERS,
				"Content-Type": "application/json",
			},
			body: JSON.stringify(body),
			signal: AbortSignal.timeout(30_000),
		});
	} catch (err) {
		printError(`Network error contacting Mem0: ${err instanceof Error ? err.message : String(err)}`);
		process.exit(1);
	}

	if (resp.status === 429) {
		printError("Rate-limited. Try again in a few minutes.");
		process.exit(1);
	}
	if (resp.status === 503) {
		printError("Agent Mode is temporarily disabled. Try again later.");
		process.exit(1);
	}
	if (!resp.ok) {
		let detail: string = resp.statusText;
		try {
			const errBody = (await resp.json()) as { error?: string };
			if (errBody.error) detail = errBody.error;
		} catch {
			/* leave detail as statusText */
		}
		printError(`Bootstrap failed: ${detail}`);
		process.exit(1);
	}

	const envelope = (await resp.json()) as BootstrapEnvelope;

	config.platform.apiKey = envelope.api_key;
	config.platform.baseUrl = baseUrl;
	config.platform.agentMode = true;
	config.platform.createdVia = "agent_mode";
	config.platform.claimedAt = "";
	config.platform.defaultUserId = envelope.default_user_id;
	// Adopt the slug-derived user_id as the default scope for memory ops.
	config.defaults.userId = envelope.default_user_id;
	saveConfig(config);

	printSuccess(`Agent Mode active. Default user_id: ${envelope.default_user_id}`);
	console.log(
		`  ${dim(`To claim this account later: ${envelope.claim_command ?? "mem0 init --email <your-email>"}`)}`,
	);
}

export async function claimViaDeviceFlow(
	config: Mem0Config,
	{ email }: { email: string },
): Promise<void> {
	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(/\/+$/, "");
	if (!config.platform.apiKey || !config.platform.agentMode) {
		printError("This command requires an active Agent Mode config. Run `mem0 init` first.");
		process.exit(1);
	}

	const cliToken = randomBytes(32).toString("base64url");
	const rawKey = config.platform.apiKey;

	// 1. CLI initiates with claim_for_apikey
	let initResp: Response;
	try {
		initResp = await fetch(`${baseUrl}/api/v1/accounts/cli_login/`, {
			method: "POST",
			headers: {
				...SOURCE_HEADERS,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ token: cliToken, claim_for_apikey: rawKey }),
			signal: AbortSignal.timeout(30_000),
		});
	} catch (err) {
		printError(`Could not initiate claim: ${err instanceof Error ? err.message : String(err)}`);
		process.exit(1);
	}

	if (!initResp.ok) {
		let detail: string = initResp.statusText;
		try {
			const errBody = (await initResp.json()) as { error?: string };
			if (errBody.error) detail = errBody.error;
		} catch {
			/* statusText fallback */
		}
		printError(`Could not initiate claim: ${detail}`);
		process.exit(1);
	}

	const initBody = (await initResp.json()) as { login_url?: string };
	const loginUrl = initBody.login_url ?? "";
	printInfo("Open in your browser to claim:");
	console.log(`  ${dim(loginUrl)}`);
	// Best-effort open in the user's browser — fall back to printing the URL.
	try {
		const { default: open } = await import("open");
		await open(loginUrl);
	} catch {
		/* user has the URL printed above */
	}

	// 2. Poll for completion
	const deadline = Date.now() + POLL_TIMEOUT_MS;
	while (Date.now() < deadline) {
		await sleep(POLL_INTERVAL_MS);

		let poll: Response;
		try {
			poll = await fetch(`${baseUrl}/api/v1/accounts/get_api_key_from_cli_token/`, {
				method: "POST",
				headers: {
					...SOURCE_HEADERS,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ token: cliToken }),
				signal: AbortSignal.timeout(15_000),
			});
		} catch {
			continue; // transient — keep polling
		}

		if (!poll.ok) {
			let err = "";
			try {
				const errBody = (await poll.json()) as { error?: string };
				err = errBody.error ?? "";
			} catch {
				/* ignore */
			}
			if (err.toLowerCase().includes("expired")) {
				printError("Claim link expired. Run `mem0 init --email <addr>` again.");
				process.exit(1);
			}
			continue;
		}

		const body = (await poll.json()) as { claimed?: boolean; claimed_at?: string };
		if (body.claimed) {
			config.platform.agentMode = false;
			config.platform.claimedAt = body.claimed_at ?? new Date().toISOString();
			config.platform.userEmail = email;
			config.platform.createdVia = "email";
			saveConfig(config);
			printSuccess(`Agent claimed to ${email}. Your API key is unchanged.`);
			return;
		}
	}

	printError("Claim timed out. Run `mem0 init --email <addr>` again.");
	process.exit(1);
}
