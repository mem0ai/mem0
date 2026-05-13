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

export async function bootstrapViaBackend(
	config: Mem0Config,
	{ source }: { source?: string | null } = {},
): Promise<void> {
	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(
		/\/+$/,
		"",
	);
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
				`  ${dim("Tip: this email already has a Mem0 account. Sign in there and run `mem0 link <key>` to attach this agent.")}`,
			);
		}
		process.exit(1);
	}

	const body = (await verifyResp.json()) as {
		claimed?: boolean;
		claimed_at?: string;
	};
	if (!body.claimed) {
		printError(`Unexpected verify response: ${JSON.stringify(body)}`);
		process.exit(1);
	}

	config.platform.agentMode = false;
	config.platform.claimedAt = body.claimed_at ?? new Date().toISOString();
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
