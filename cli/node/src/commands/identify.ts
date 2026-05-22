/**
 * mem0 identify — declare which agent owns the current agent-mode key.
 *
 * Used when `mem0 init --agent` ran without --agent-caller, so the backend
 * saved agent_caller=NULL. The agent re-runs `mem0 identify <name>` to PATCH
 * its own row with its real identity. Idempotent.
 */

import { printError, printSuccess } from "../branding.js";
import { loadConfig, saveConfig } from "../config.js";

const SOURCE_HEADERS = {
	"X-Mem0-Source": "cli",
	"X-Mem0-Client-Language": "node",
} as const;

export async function runIdentify(name: string): Promise<void> {
	const config = loadConfig();
	if (!config.platform.apiKey) {
		printError("No API key configured. Run `mem0 init --agent` first.");
		process.exit(1);
	}
	if (!config.platform.agentMode) {
		printError("This command only works on unclaimed agent-mode keys.");
		process.exit(1);
	}

	const clean = (name ?? "").trim();
	if (!clean) {
		printError("Agent name is required.");
		process.exit(1);
	}

	const baseUrl = (config.platform.baseUrl || "https://api.mem0.ai").replace(
		/\/+$/,
		"",
	);

	let resp: Response;
	try {
		resp = await fetch(`${baseUrl}/api/v1/auth/agent_mode/caller/`, {
			method: "PATCH",
			headers: {
				...SOURCE_HEADERS,
				Authorization: `Token ${config.platform.apiKey}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ agent_caller: clean }),
			signal: AbortSignal.timeout(30_000),
		});
	} catch (err) {
		printError(
			`Network error: ${err instanceof Error ? err.message : String(err)}`,
		);
		process.exit(1);
	}

	if (!resp.ok) {
		let detail: string = resp.statusText;
		try {
			const body = (await resp.json()) as { error?: string };
			if (body.error) detail = body.error;
		} catch {
			/* leave as statusText */
		}
		printError(`Identify failed: ${detail}`);
		process.exit(1);
	}

	const body = (await resp.json()) as { agent_caller?: string };
	const canonical = body.agent_caller ?? clean;
	config.platform.agentCaller = canonical;
	saveConfig(config);
	printSuccess(`Identified as ${canonical}.`);
}
