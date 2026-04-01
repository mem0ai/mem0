/**
 * mem0 init — interactive setup wizard.
 */

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
	DEFAULT_BASE_URL,
	type Mem0Config,
	createDefaultConfig,
	loadConfig,
	saveConfig,
} from "../config.js";

const { brand, dim } = colors;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function validateEmail(email: string): void {
	if (!EMAIL_RE.test(email)) {
		printError(`Invalid email address: ${JSON.stringify(email)}`);
		process.exit(1);
	}
}

async function emailLogin(
	email: string,
	code: string | undefined,
	baseUrl: string,
): Promise<Record<string, unknown>> {
	const url = baseUrl.replace(/\/+$/, "");
	let codeValue = code;

	if (!codeValue) {
		const resp = await fetch(`${url}/api/v1/auth/email_code/`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
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
		headers: { "Content-Type": "application/json" },
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
		`  ${dim("Get your API key at https://app.mem0.ai/dashboard/api-keys")}`,
	);
	console.log();

	process.stdout.write(`  ${brand("API Key")}: `);
	const apiKey = await promptSecret("");
	if (!apiKey) {
		printError("API key is required.");
		process.exit(1);
	}
	config.platform.apiKey = apiKey;
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
		} else {
			printError(
				`Could not connect: ${status.error ?? "Unknown error"}`,
				"Visit https://app.mem0.ai/dashboard/api-keys to get a new key, or run mem0 init again.",
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
	} = {},
): Promise<void> {
	const config = createDefaultConfig();
	const savedConfig = loadConfig();
	const baseUrl =
		process.env.MEM0_BASE_URL ||
		savedConfig.platform.baseUrl ||
		DEFAULT_BASE_URL;

	// Guards
	if (opts.code && !opts.email) {
		printError("--code requires --email.");
		process.exit(1);
	}
	if (opts.email && opts.apiKey) {
		printError("Cannot use both --api-key and --email.");
		process.exit(1);
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

	// Non-interactive: both flags provided
	if (opts.apiKey && opts.userId) {
		config.platform.apiKey = opts.apiKey;
		config.defaults.userId = opts.userId;
		await validatePlatform(config);
		saveConfig(config);
		printSuccess("Configuration saved to ~/.mem0/config.json");
		return;
	}

	// Non-TTY without full flags: error with usage hint
	if (!process.stdin.isTTY && (!opts.apiKey || !opts.userId)) {
		printError(
			"Non-interactive terminal detected and missing required flags.",
			"Usage: mem0 init --api-key <key> --user-id <id>",
		);
		process.exit(1);
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
