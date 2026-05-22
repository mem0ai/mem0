/**
 * Agent Mode commands — bootstrap (unattended signup) and OTP-based claim.
 */

import readline from "node:readline";
import { colors, printError, printInfo, printSuccess } from "../branding.js";
import { type Mem0Config, saveConfig } from "../config.js";

const { brand, dim } = colors;

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
	mem0_notice?: string;
}

function isValidEnvelope(v: unknown): v is BootstrapEnvelope {
	return (
		!!v &&
		typeof v === "object" &&
		typeof (v as BootstrapEnvelope).api_key === "string" &&
		(v as BootstrapEnvelope).api_key.length > 0 &&
		typeof (v as BootstrapEnvelope).default_user_id === "string" &&
		(v as BootstrapEnvelope).default_user_id.length > 0
	);
}

/**
 * POST /api/v1/auth/agent_mode/ and mutate config in place.
 *
 * @param config - Mem0Config mutated in place with the new platform values.
 * @param source - `--source` flag passthrough (analytics tag, free-form).
 * @param agentCaller - Self-declared agent identity passed via `--agent-caller`
 *   (e.g. `claude-code`, `cursor`). May be null when the caller omitted the
 *   flag; the agent can backfill later via `mem0 identify <name>`. Sent to the
 *   backend in the request body and saved into `platform.agentCaller` for
 *   local introspection.
 */
export async function bootstrapViaBackend(
	config: Mem0Config,
	{
		source,
		agentCaller,
	}: { source?: string | null; agentCaller?: string | null } = {},
): Promise<void> {
	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(
		/\/+$/,
		"",
	);
	const body: Record<string, unknown> = {};
	if (source) body.source = source;
	if (agentCaller) body.agent_caller = agentCaller;

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
		printError(
			`Network error contacting Mem0: ${err instanceof Error ? err.message : String(err)}`,
		);
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
			const errBody = (await resp.json()) as {
				error?: string;
				detail?: string;
			};
			detail = errBody.error ?? errBody.detail ?? resp.statusText;
		} catch {
			/* leave detail as statusText */
		}
		// Backend's @ratelimit decorator raises PermissionDenied, which DRF
		// translates to a generic 403 "You do not have permission to perform
		// this action." That's opaque — surface it as the rate-limit message
		// it actually is.
		if (resp.status === 403 && /permission/i.test(detail)) {
			printError(
				"Daily Agent Mode signup limit reached for this network (5/day). Try again from a different IP or after midnight UTC.",
			);
			process.exit(1);
		}
		printError(`Bootstrap failed: ${detail}`);
		process.exit(1);
	}

	const envelope = (await resp.json()) as BootstrapEnvelope;
	if (!isValidEnvelope(envelope)) {
		// Defend against partial/malformed backend responses (e.g. {api_key: null}).
		// Without this guard, the typed `string` field is silently set to
		// undefined/null and persisted, producing confusing downstream errors.
		printError(
			"Bootstrap response missing required fields — please update the CLI.",
		);
		process.exit(1);
	}

	config.platform.apiKey = envelope.api_key;
	config.platform.baseUrl = baseUrl;
	config.platform.agentMode = true;
	config.platform.createdVia = "agent_mode";
	config.platform.agentCaller = agentCaller ?? "";
	config.platform.claimedAt = "";
	config.platform.defaultUserId = envelope.default_user_id;
	// Adopt the slug-derived user_id as the default scope for memory ops.
	config.defaults.userId = envelope.default_user_id;
	saveConfig(config);

	printSuccess(
		`Agent Mode active. Default user_id: ${envelope.default_user_id}`,
	);
	if (envelope.mem0_notice) {
		console.log(`\n\x1b[33m🔔 ${envelope.mem0_notice}\x1b[0m\n`);
	} else {
		// Fallback for older backends without the unified notice field.
		const claimCmd = envelope.claim_command ?? "mem0 init --email <your-email>";
		console.log(`  ${dim(`To claim this account later: ${claimCmd}`)}`);
	}

	if (!agentCaller) {
		console.log(
			`  ${dim("If you are an AI agent, identify yourself: `mem0 identify <your-name>` (e.g. claude-code, cursor).")}`,
		);
	}
}

/**
 * Claim an existing Agent Mode account via OTP — no browser, no polling.
 *
 * Hits /api/v1/auth/email_code/ to send a verification code, prompts for it
 * interactively (or accepts via `code`), then sends it to /verify/ alongside
 * `agent_mode_api_key`. Backend's verify_email_code runs upgrade-in-place
 * inline and returns the claim result.
 */
export async function claimViaOtp(
	config: Mem0Config,
	{ email, code }: { email: string; code?: string },
): Promise<void> {
	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(
		/\/+$/,
		"",
	);
	if (!config.platform.apiKey || !config.platform.agentMode) {
		printError(
			"This command requires an active Agent Mode config. Run `mem0 init` first.",
		);
		process.exit(1);
	}

	const rawKey = config.platform.apiKey;

	// Step 1: request OTP (unless --code was supplied)
	if (!code) {
		const sendResp = await fetch(`${baseUrl}/api/v1/auth/email_code/`, {
			method: "POST",
			headers: { ...SOURCE_HEADERS, "Content-Type": "application/json" },
			body: JSON.stringify({ email }),
			signal: AbortSignal.timeout(30_000),
		});
		if (sendResp.status === 429) {
			printError("Too many attempts. Try again in a few minutes.");
			process.exit(1);
		}
		if (!sendResp.ok) {
			let detail: string = sendResp.statusText;
			try {
				const errBody = (await sendResp.json()) as { error?: string };
				if (errBody.error) detail = errBody.error;
			} catch {
				/* leave as statusText */
			}
			printError(`Failed to send code: ${detail}`);
			process.exit(1);
		}

		printSuccess(`Verification code sent to ${email}. Check your inbox.`);

		if (!process.stdin.isTTY) {
			printError(
				"No --code provided and terminal is non-interactive.",
				`Re-run: mem0 init --email ${email} --code <code>`,
			);
			process.exit(1);
		}

		console.log();
		code = await promptLine(`  ${brand("Verification Code")}`);
		if (!code) {
			printError("Code is required.");
			process.exit(1);
		}
	}

	// Step 2: verify + claim atomically
	const verifyResp = await fetch(`${baseUrl}/api/v1/auth/email_code/verify/`, {
		method: "POST",
		headers: { ...SOURCE_HEADERS, "Content-Type": "application/json" },
		body: JSON.stringify({
			email,
			code: code.trim(),
			agent_mode_api_key: rawKey,
		}),
		signal: AbortSignal.timeout(30_000),
	});

	if (!verifyResp.ok) {
		let detail: string = verifyResp.statusText;
		let errCode = "";
		try {
			const errBody = (await verifyResp.json()) as {
				error?: string;
				code?: string;
			};
			if (errBody.error) detail = errBody.error;
			if (errBody.code) errCode = errBody.code;
		} catch {
			/* leave as statusText */
		}
		printError(`Claim failed: ${detail}`);
		if (errCode === "email_already_claimed") {
			console.log(
				`  ${dim("Tip: this email already has a Mem0 account. Sign in at app.mem0.ai with your existing credentials.")}`,
			);
		}
		process.exit(1);
	}

	const claimBody = (await verifyResp.json()) as {
		claimed?: boolean;
		claimed_at?: string;
	};
	if (!claimBody.claimed) {
		printError(`Unexpected verify response: ${JSON.stringify(claimBody)}`);
		process.exit(1);
	}

	config.platform.agentMode = false;
	config.platform.claimedAt = claimBody.claimed_at ?? new Date().toISOString();
	config.platform.userEmail = email;
	config.platform.createdVia = "email";
	saveConfig(config);

	printSuccess(`Agent claimed to ${email}. Your API key is unchanged.`);
}

function promptLine(label: string): Promise<string> {
	const rl = readline.createInterface({
		input: process.stdin,
		output: process.stdout,
	});
	return new Promise((resolve) => {
		rl.question(`${label}: `, (answer) => {
			rl.close();
			resolve(answer.trim());
		});
	});
}
