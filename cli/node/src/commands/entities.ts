/**
 * Entity management commands.
 */

import readline from "node:readline";
import Table from "cli-table3";
import type { Backend } from "../backend/base.js";
import {
	colors,
	printError,
	printInfo,
	printSuccess,
	timedStatus,
} from "../branding.js";
import { formatAgentEnvelope, formatJson } from "../output.js";
import { setCurrentCommand } from "../state.js";

const { brand, accent, dim } = colors;

const VALID_TYPES = new Set(["users", "agents", "apps", "runs"]);

export async function cmdEntitiesList(
	backend: Backend,
	entityType: string,
	opts: { output: string },
): Promise<void> {
	setCurrentCommand("entity list");
	if (!VALID_TYPES.has(entityType)) {
		printError(
			`Invalid entity type: ${entityType}. Use: ${[...VALID_TYPES].join(", ")}`,
		);
		process.exit(1);
	}

	const start = performance.now();
	let results: Record<string, unknown>[];
	try {
		results = await timedStatus(`Fetching ${entityType}...`, async () => {
			return backend.entities(entityType);
		});
	} catch (e) {
		printError(
			e instanceof Error ? e.message : String(e),
			"This feature may require the mem0 Platform.",
		);
		process.exit(1);
	}
	const elapsed = (performance.now() - start) / 1000;

	if (opts.output === "agent" || opts.output === "json") {
		formatAgentEnvelope({
			command: "entity list",
			data: results,
			count: results.length,
			durationMs: Math.round(elapsed * 1000),
		});
		return;
	}

	if (!results.length) {
		printInfo(`No ${entityType} found.`);
		return;
	}

	const table = new Table({
		head: [accent("Name / ID"), accent("Created")],
		style: { head: [], border: [] },
	});

	for (const entity of results) {
		const name = String(entity.name ?? entity.id ?? "—");
		const created = String(entity.created_at ?? "—").slice(0, 10);
		table.push([name, created]);
	}

	console.log();
	console.log(table.toString());
	console.log(
		`  ${dim(`${results.length} ${entityType} (${elapsed.toFixed(2)}s)`)}`,
	);
	console.log();
}

export async function cmdEntitiesDelete(
	backend: Backend,
	opts: {
		userId?: string;
		agentId?: string;
		appId?: string;
		runId?: string;
		dryRun?: boolean;
		force: boolean;
		output: string;
	},
): Promise<void> {
	setCurrentCommand("entity delete");
	const { isAgentMode } = await import("../state.js");
	if (isAgentMode() && !opts.force) {
		printError("Destructive operation requires --force in agent mode.");
		process.exit(1);
	}
	if (!opts.userId && !opts.agentId && !opts.appId && !opts.runId) {
		printError(
			"Provide at least one of --user-id, --agent-id, --app-id, --run-id.",
		);
		process.exit(1);
	}

	const scopeParts: string[] = [];
	if (opts.userId) scopeParts.push(`user=${opts.userId}`);
	if (opts.agentId) scopeParts.push(`agent=${opts.agentId}`);
	if (opts.appId) scopeParts.push(`app=${opts.appId}`);
	if (opts.runId) scopeParts.push(`run=${opts.runId}`);
	const scope = scopeParts.join(", ");

	if (opts.dryRun) {
		printInfo(`Would delete entity ${scope} and all its memories.`);
		printInfo("No changes made.");
		return;
	}

	if (!opts.force) {
		const rl = readline.createInterface({
			input: process.stdin,
			output: process.stdout,
		});
		const answer = await new Promise<string>((resolve) => {
			rl.question(
				`\n  \u26a0  Delete entity ${scope} AND all its memories? This cannot be undone. [y/N] `,
				resolve,
			);
		});
		rl.close();
		if (answer.toLowerCase() !== "y") {
			printInfo("Cancelled.");
			process.exit(0);
		}
	}

	const start = performance.now();
	let result: Record<string, unknown>;
	try {
		result = await timedStatus("Deleting entity...", async () => {
			return backend.deleteEntities({
				userId: opts.userId,
				agentId: opts.agentId,
				appId: opts.appId,
				runId: opts.runId,
			});
		});
	} catch (e) {
		printError(e instanceof Error ? e.message : String(e));
		process.exit(1);
	}
	const elapsed = (performance.now() - start) / 1000;

	if (opts.output === "agent") {
		formatAgentEnvelope({
			command: "entity delete",
			data: { deleted: true },
			durationMs: Math.round(elapsed * 1000),
		});
	} else if (opts.output === "json") {
		formatJson(result);
	} else if (opts.output !== "quiet") {
		printSuccess(`Entity deleted with all memories (${elapsed.toFixed(2)}s)`);
	}
}
