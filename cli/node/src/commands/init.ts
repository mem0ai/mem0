/**
 * mem0 init — interactive setup wizard.
 */

import fs from "node:fs";
import readline from "node:readline";
import { PlatformBackend } from "../backend/platform.js";
import {
	colors,
	printBanner,
	printError,
	printInfo,
	printSuccess,
} from "../branding.js";
import {
	CONFIG_FILE,
	DEFAULT_BASE_URL,
	type Mem0Config,
	createDefaultConfig,
	loadConfig,
	redactKey,
	saveConfig,
} from "../config.js";
import { formatJsonEnvelope } from "../output.js";
import { isAgentMode } from "../state.js";

const { brand, dim } = colors;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function validateEmail(email: string): void {
	if (!EMAIL_RE.test(email)) {
		printError(`Invalid email address: ${JSON.stringify(email)}`);
		process.exit(1);
	}
}

/** @internal — exported for unit tests. */
export async function pingKey(
	apiKey: string,
	baseUrl: string,
	timeoutMs = 5000,
): Promise<boolean> {
	// Returns false ONLY on a definitive "invalid key" signal (HTTP 401/403).
	// Network errors, timeouts, and 5xx responses return true so we prefer
	// reusing an existing key over silently minting a new shadow on a transient
	// blip (which would also clobber config + plugin-sync targets).
	try {
		const resp = await fetch(`${baseUrl.replace(/\/+$/, "")}/v1/ping/`, {
			headers: { Authorization: `Token ${apiKey}` },
			signal: AbortSignal.timeout(timeoutMs),
		});
		return resp.status !== 401 && resp.status !== 403;
	} catch {
		return true; // unknown — prefer reuse
	}
}

async function maybeIdentify(
	key: string,
	baseUrl: string,
	agentCaller: string | undefined,
): Promise<void> {
	// Best-effort PATCH agent_caller when --agent-caller is supplied on a
	// reused key. Silent no-op on any failure — reuse must not break.
	if (!agentCaller) return;
	try {
		const resp = await fetch(
			`${baseUrl.replace(/\/+$/, "")}/api/v1/auth/agent_mode/caller/`,
			{
				method: "PATCH",
				headers: {
					Authorization: `Token ${key}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ agent_caller: agentCaller }),
				signal: AbortSignal.timeout(10_000),
			},
		);
		if (resp.ok) {
			try {
				const body = (await resp.json()) as { agent_caller?: string };
				if (fs.existsSync(CONFIG_FILE)) {
					const cfg = loadConfig();
					cfg.platform.agentCaller = body.agent_caller ?? agentCaller;
					saveConfig(cfg);
				}
			} catch {
				/* swallow — best effort */
			}
		}
	} catch {
		/* swallow — best effort */
	}
}

async function emailLogin(
	email: string,
	code: string | undefined,
	baseUrl: string,
): Promise<Record<string, unknown>> {
	const url = baseUrl.replace(/\/+$/, "");
	let codeValue = code;

	const sourceHeaders = {
		"Content-Type": "application/json",
		"X-Mem0-Source": "cli",
		"X-Mem0-Client-Language": "node",
	};

	if (!codeValue) {
		const resp = await fetch(`${url}/api/v1/auth/email_code/`, {
			method: "POST",
			headers: sourceHeaders,
			body: JSON.stringify({ email }),
			signal: AbortSignal.timeout(30_000),
		});
		if (resp.status === 429) {
			printError("Too many attempts. Try again in a few minutes.");
			process.exit(1);
		}
		if (!resp.ok) {
			let detail: string;
			try {
				const body = (await resp.json()) as Record<string, unknown>;
				detail = (body.error ?? body.detail ?? resp.statusText) as string;
			} catch {
				detail = resp.statusText;
			}
			printError(`Failed to send code: ${detail}`);
			process.exit(1);
		}

		printSuccess("Verification code sent! Check your email.");

		if (!process.stdin.isTTY) {
			printError(
				"No --code provided and terminal is non-interactive.",
				"Run: mem0 init --email <email> --code <code>",
			);
			process.exit(1);
		}

		console.log();
		const entered = await promptLine(`  ${brand("Verification Code")}`);
		if (!entered) {
			printError("Code is required.");
			process.exit(1);
		}
		codeValue = entered;
	}

	const verifyResp = await fetch(`${url}/api/v1/auth/email_code/verify/`, {
		method: "POST",
		headers: sourceHeaders,
		body: JSON.stringify({ email, code: codeValue.trim() }),
		signal: AbortSignal.timeout(30_000),
	});
	if (verifyResp.status === 429) {
		printError("Too many attempts. Try again in a few minutes.");
		process.exit(1);
	}
	if (!verifyResp.ok) {
		let detail: string;
		try {
			const body = (await verifyResp.json()) as Record<string, unknown>;
			detail = (body.error ?? body.detail ?? verifyResp.statusText) as string;
		} catch {
			detail = verifyResp.statusText;
		}
		printError(`Verification failed: ${detail}`);
		process.exit(1);
	}

	return verifyResp.json() as Promise<Record<string, unknown>>;
}

function promptSecret(label: string): Promise<string> {
	return new Promise((resolve, reject) => {
		process.stdout.write(label);

		if (process.stdin.isTTY) {
			process.stdin.setRawMode(true);
		}
		process.stdin.resume();
		process.stdin.setEncoding("utf-8");

		const chars: string[] = [];

		const onData = (key: string) => {
			for (const ch of key) {
				if (ch === "\r" || ch === "\n") {
					cleanup();
					process.stdout.write("\n");
					resolve(chars.join(""));
					return;
				}
				if (ch === "\x03") {
					cleanup();
					reject(new Error("Interrupted"));
					return;
				}
				if (ch === "\x7f" || ch === "\x08") {
					// backspace
					if (chars.length > 0) {
						chars.pop();
						process.stdout.write("\b \b");
					}
				} else if (ch === "\x15") {
					// Ctrl+U — clear line
					process.stdout.write("\b \b".repeat(chars.length));
					chars.length = 0;
				} else if (ch >= " ") {
					chars.push(ch);
					process.stdout.write("*");
				}
			}
		};

		const cleanup = () => {
			process.stdin.removeListener("data", onData);
			if (process.stdin.isTTY) {
				process.stdin.setRawMode(false);
			}
			process.stdin.pause();
		};

		process.stdin.on("data", onData);
	});
}

function promptLine(label: string, defaultValue?: string): Promise<string> {
	const rl = readline.createInterface({
		input: process.stdin,
		output: process.stdout,
	});
	const prompt = defaultValue ? `${label} [${defaultValue}]: ` : `${label}: `;
	return new Promise((resolve) => {
		rl.question(prompt, (answer) => {
			rl.close();
			resolve(answer.trim() || defaultValue || "");
		});
	});
}

async function setupPlatform(config: Mem0Config): Promise<void> {
	console.log();
	console.log(
		`  ${dim("Get your API key at https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=cli-node")}`,
	);
	console.log();

	process.stdout.write(`  ${brand("API Key")}: `);
	const apiKey = await promptSecret("");
	if (!apiKey) {
		printError("API key is required.");
		process.exit(1);
	}
	config.platform.apiKey = apiKey;
	config.platform.createdVia = "api_key";
}

async function setupDefaults(config: Mem0Config): Promise<void> {
	console.log();
	printInfo("Set default entity IDs (press Enter to skip).\n");

	const _systemUser = process.env.USER || process.env.USERNAME || "mem0-cli";
	const userId = await promptLine(
		`  ${brand("Default User ID")} ${dim("(recommended)")}`,
		_systemUser,
	);
	if (userId) config.defaults.userId = userId;
}

async function validatePlatform(config: Mem0Config): Promise<void> {
	console.log();
	printInfo("Validating connection...");
	try {
		const backend = new PlatformBackend(config.platform);
		const status = await backend.status({
			userId: config.defaults.userId || undefined,
			agentId: config.defaults.agentId || undefined,
		});
		if (status.connected) {
			printSuccess("Connected to mem0 Platform!");
			// Cache user_email from ping response for telemetry distinct_id
			try {
				const pingData = (await backend.ping()) as Record<string, unknown>;
				const userEmail = pingData?.user_email as string | undefined;
				if (userEmail) {
					config.platform.userEmail = userEmail;
				}
			} catch {
				/* ignore — telemetry ID will fall back to API key hash */
			}
		} else {
			printError(
				`Could not connect: ${status.error ?? "Unknown error"}`,
				"Visit https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=cli-node to get a new key, or run mem0 init again.",
			);
		}
	} catch (e) {
		printError(`Connection test failed: ${e instanceof Error ? e.message : e}`);
	}
}

export async function runInit(
	opts: {
		apiKey?: string;
		userId?: string;
		email?: string;
		code?: string;
		force?: boolean;
		agent?: boolean;
		source?: string;
		agentCaller?: string;
	} = {},
): Promise<void> {
	const { detectAgentCaller } = await import("../agent-detect.js");
	const { bootstrapViaBackend, claimViaOtp } = await import("./agent-mode.js");
	const { isAgentMode } = await import("../state.js");
	const { captureEvent } = await import("../telemetry.js");

	const fireInit = (
		mode: "agent" | "email" | "api_key" | "existing_key",
		claimed = false,
	) => {
		const props: Record<string, unknown> = { command: "init", mode };
		// Self-declared via --agent-caller; not sniffed from env vars.
		if (opts.agentCaller) props.agent_caller = opts.agentCaller;
		if (opts.source) props.signup_source = opts.source;
		if (claimed) props.claimed_agent_mode = true;
		captureEvent("cli.init", props);
	};

	const config = createDefaultConfig();
	const savedConfig = loadConfig();
	const baseUrl =
		process.env.MEM0_BASE_URL ||
		savedConfig.platform.baseUrl ||
		DEFAULT_BASE_URL;
	config.platform.baseUrl = baseUrl;

	// Guards
	if (opts.code && !opts.email) {
		printError("--code requires --email.");
		process.exit(1);
	}
	if (opts.email && opts.apiKey) {
		printError("Cannot use both --api-key and --email.");
		process.exit(1);
	}

	// ── Claim flow: --email against an existing agent-mode config ───────────
	if (
		opts.email &&
		fs.existsSync(CONFIG_FILE) &&
		savedConfig.platform.agentMode &&
		savedConfig.platform.apiKey
	) {
		const email = opts.email.trim().toLowerCase();
		validateEmail(email);
		printInfo(`Claiming Agent Mode account to ${email}...`);
		await claimViaOtp(savedConfig, { email, code: opts.code });
		fireInit("email", true);
		return;
	}

	// ── Agent Mode path runs BEFORE the existing-config guard ──────────────
	// Rule 1/2 will REUSE a valid existing key (not overwrite), so we must
	// short-circuit before the guard prompts the user about overwriting.
	// Rule 3 only mints when there's no valid key to reuse — in that case
	// overwriting is what the user wants.
	const agentCtx =
		opts.agent === true || isAgentMode() || detectAgentCaller() !== null;
	if (!opts.apiKey && !opts.email && agentCtx) {
		const emitReuseEnvelope = (source: "env" | "config") => {
			if (isAgentMode()) {
				formatJsonEnvelope({
					command: "init",
					data: {
						api_key_saved: false,
						api_key_source: source,
						agent_mode: false,
						message:
							"Existing Mem0 API key found and reused. No Agent Mode key was created.",
					},
				});
			} else {
				printSuccess(
					source === "env"
						? "Existing MEM0_API_KEY is valid; reusing it. No new Agent Mode key was minted."
						: "Existing API key in config is valid; reusing it. No new Agent Mode key was minted.",
				);
			}
		};
		// Rule 1: env MEM0_API_KEY valid → reuse, no new key.
		const envKey = (process.env.MEM0_API_KEY || "").trim();
		if (envKey && (await pingKey(envKey, baseUrl))) {
			await maybeIdentify(envKey, baseUrl, opts.agentCaller);
			emitReuseEnvelope("env");
			fireInit("existing_key");
			return;
		}
		// Rule 2: existing config api_key valid → reuse.
		if (
			savedConfig.platform.apiKey &&
			(await pingKey(savedConfig.platform.apiKey, baseUrl))
		) {
			await maybeIdentify(
				savedConfig.platform.apiKey,
				baseUrl,
				opts.agentCaller,
			);
			emitReuseEnvelope("config");
			fireInit("existing_key");
			return;
		}
		// Rule 3: mint a fresh shadow (no valid key to reuse).
		// agent_caller is self-declared via --agent-caller (Proof Editor-style),
		// not derived from env-var sniffing. detectAgentCaller() above is still
		// used as a context trigger (does this look like an agent?) but never
		// to fill identity.
		await bootstrapViaBackend(config, {
			source: opts.source ?? null,
			agentCaller: opts.agentCaller ?? null,
		});
		fireInit("agent");
		return;
	}

	// Warn if an existing config with an API key would be overwritten
	if (
		!opts.force &&
		fs.existsSync(CONFIG_FILE) &&
		savedConfig.platform.apiKey
	) {
		console.log(
			`\n  ${brand("Existing configuration found")} ${dim(`(API key: ${redactKey(savedConfig.platform.apiKey)})`)}`,
		);
		if (process.stdin.isTTY) {
			const rl = readline.createInterface({
				input: process.stdin,
				output: process.stdout,
			});
			const answer = await new Promise<string>((resolve) => {
				rl.question(
					"  Overwrite existing config? This cannot be undone. [y/N] ",
					resolve,
				);
			});
			rl.close();
			if (answer.toLowerCase() !== "y") {
				printInfo("Cancelled. Use --force to skip this check.");
				process.exit(0);
			}
		} else {
			printError(
				"Existing config would be overwritten.",
				"Use --force to overwrite.",
			);
			process.exit(1);
		}
	}

	// ── Email login flow ──────────────────────────────────────────────────────
	if (opts.email) {
		const email = opts.email.trim().toLowerCase();
		validateEmail(email);

		printBanner();
		console.log();
		printInfo(`Logging in as ${email}...\n`);

		const result = await emailLogin(email, opts.code, baseUrl);

		const apiKeyVal = result.api_key as string | undefined;
		if (!apiKeyVal) {
			printError(
				"Auth succeeded but no API key was returned. Contact support.",
			);
			process.exit(1);
		}

		config.platform.apiKey = apiKeyVal;
		config.platform.baseUrl = baseUrl;
		config.platform.userEmail = email;
		config.platform.createdVia = "email";
		config.defaults.userId =
			opts.userId || process.env.USER || process.env.USERNAME || "mem0-cli";

		saveConfig(config);
		console.log();
		printSuccess("Authenticated! Configuration saved to ~/.mem0/config.json");
		console.log();
		console.log(`  ${dim("Get started:")}`);
		console.log(`  ${dim('  mem0 add "I prefer dark mode"')}`);
		console.log(`  ${dim('  mem0 search "preferences"')}`);
		console.log();
		return;
	}

	// ── API key flow ──────────────────────────────────────────────────────────
	// (Agent Mode branch runs earlier — see above, before the existing-config
	// guard, so Rules 1/2 can REUSE a valid key without prompting overwrite.)

	// Non-TTY: resolve defaults so partial flags work in pipelines / CI
	if (!process.stdin.isTTY) {
		if (!opts.apiKey) {
			printError(
				"Non-interactive terminal detected and --api-key is required.",
				"Usage: mem0 init --api-key <key>, --email <addr>, or --agent for unattended Agent Mode bootstrap.",
			);
			process.exit(1);
		}
		opts.userId =
			opts.userId || process.env.USER || process.env.USERNAME || "mem0-cli";
	}

	// Non-interactive: both flags provided
	if (opts.apiKey && opts.userId) {
		config.platform.apiKey = opts.apiKey;
		config.platform.createdVia = "api_key";
		config.defaults.userId = opts.userId;
		await validatePlatform(config);
		saveConfig(config);
		printSuccess("Configuration saved to ~/.mem0/config.json");
		return;
	}

	printBanner();
	console.log();
	printInfo("Welcome! Let's set up your mem0 CLI.\n");

	// Use provided API key or prompt
	if (opts.apiKey) {
		config.platform.apiKey = opts.apiKey;
	} else {
		console.log(`  ${brand("How would you like to authenticate?")}`);
		console.log(`  ${dim("1.")} Login with email ${dim("(recommended)")}`);
		console.log(`  ${dim("2.")} Enter API key manually`);
		console.log();

		const choice = await promptLine(`  ${brand("Choose")} [1/2]`, "1");

		if (choice === "1") {
			console.log();
			const emailAddr = await promptLine(`  ${brand("Email")}`);
			if (!emailAddr) {
				printError("Email is required.");
				process.exit(1);
			}

			const email = emailAddr.trim().toLowerCase();
			validateEmail(email);
			printInfo(`Logging in as ${email}...\n`);

			const result = await emailLogin(email, undefined, baseUrl);

			const apiKeyVal = result.api_key as string | undefined;
			if (!apiKeyVal) {
				printError(
					"Auth succeeded but no API key was returned. Contact support.",
				);
				process.exit(1);
			}

			config.platform.apiKey = apiKeyVal;
			config.platform.baseUrl = baseUrl;
			config.platform.userEmail = email;
			config.platform.createdVia = "email";
			config.defaults.userId =
				opts.userId || process.env.USER || process.env.USERNAME || "mem0-cli";

			saveConfig(config);
			console.log();
			printSuccess("Authenticated! Configuration saved to ~/.mem0/config.json");
			console.log();
			console.log(`  ${dim("Get started:")}`);
			console.log(`  ${dim('  mem0 add "I prefer dark mode"')}`);
			console.log(`  ${dim('  mem0 search "preferences"')}`);
			console.log();
			return;
		}

		// choice === "2": fall through to API key prompt
		await setupPlatform(config);
	}

	// Use provided user ID or prompt
	if (opts.userId) {
		config.defaults.userId = opts.userId;
	} else {
		await setupDefaults(config);
	}

	await validatePlatform(config);

	saveConfig(config);
	console.log();
	printSuccess("Configuration saved to ~/.mem0/config.json");
	console.log();
	console.log(`  ${dim("Get started:")}`);
	if (config.defaults.userId) {
		console.log(`  ${dim('  mem0 add "I prefer dark mode"')}`);
		console.log(`  ${dim('  mem0 search "preferences"')}`);
	} else {
		console.log(`  ${dim('  mem0 add "I prefer dark mode" --user-id alice')}`);
		console.log(`  ${dim('  mem0 search "preferences" --user-id alice')}`);
	}
	console.log();
}
