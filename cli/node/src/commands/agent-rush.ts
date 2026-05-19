/**
 * `mem0 agent-rush <add|search> "..."` — wraps the AGENTRUSH platform endpoints.
 * Project routing is implicit (server-side); zero flags needed.
 */

import { colors, printError, printSuccess } from "../branding.js";
import { loadConfig } from "../config.js";
import { CLI_VERSION } from "../version.js";

const ERROR_HINTS: Record<string, string> = {
	agentrush_search_first:
		"Run 3 'mem0 agent-rush search' commands before adding.",
	agentrush_search_quota: "You've used your 3 lifetime searches.",
	agentrush_add_quota: "You've used your 3 lifetime adds.",
	agentrush_not_agent_mode:
		"Re-run 'mem0 init --agent' to bootstrap an agent-mode key.",
	agentrush_length: "Memory text must be 50-1000 characters.",
	agentrush_no_urls: "URLs are not allowed.",
	agentrush_blocklist: "Content contains a blocked term.",
	agentrush_global_quota: "Event-wide cap reached. Try again later.",
	agentrush_not_provisioned:
		"AGENTRUSH is not provisioned in this environment.",
};

async function callEndpoint(
	path: string,
	body: Record<string, unknown>,
): Promise<unknown> {
	const config = loadConfig();
	const baseUrl = (config.platform?.baseUrl ?? "https://api.mem0.ai").replace(
		/\/+$/,
		"",
	);

	if (!config.platform?.apiKey) {
		printError("Not initialized. Run `mem0 init --agent` first.");
		process.exit(1);
	}

	const resp = await fetch(`${baseUrl}${path}`, {
		method: "POST",
		headers: {
			Authorization: `Token ${config.platform.apiKey}`,
			"Content-Type": "application/json",
			"X-Mem0-Source": "cli",
			"X-Mem0-Client-Language": "node",
			"X-Mem0-Client-Version": CLI_VERSION,
			"X-Mem0-Mode": "agent-rush",
		},
		body: JSON.stringify(body),
		signal: AbortSignal.timeout(30_000),
	});

	const json = await resp.json().catch(() => ({}));

	if (!resp.ok) {
		const code =
			(json as { error?: { code?: string } }).error?.code ?? "unknown";
		printError(`AGENTRUSH error: ${code}`);
		if (ERROR_HINTS[code]) {
			console.log(`  ${colors.dim(ERROR_HINTS[code])}`);
		}
		process.exit(1);
	}

	return json;
}

export async function cmdAgentRushAdd(content: string): Promise<void> {
	const result = await callEndpoint("/v1/agent-rush/memories/", { content });
	printSuccess(
		`Memory submitted (event_id: ${(result as { event_id?: string }).event_id ?? "?"})`,
	);
}

export async function cmdAgentRushSearch(query: string): Promise<void> {
	const result = (await callEndpoint("/v1/agent-rush/memories/search/", {
		query,
	})) as {
		results?: Array<{ memory?: string }>;
		memories?: Array<{ memory?: string }>;
	};

	const memories = result.results ?? result.memories ?? [];

	if (memories.length === 0) {
		console.log(colors.dim("(no results)"));
		return;
	}

	memories.slice(0, 5).forEach((m, i) => {
		console.log(`  ${i + 1}. ${m.memory ?? JSON.stringify(m)}`);
	});
}
