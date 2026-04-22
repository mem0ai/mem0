#!/usr/bin/env node

/**
 * Main CLI application — the entrypoint for `mem0`.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Command } from "commander";
import { AuthError, type Backend, getBackend } from "./backend/index.js";
import { colors, printError, printWarning } from "./branding.js";
import type { Mem0Config } from "./config.js";
import { loadConfig, saveConfig } from "./config.js";
import { richFormatHelp } from "./help.js";
import { setAgentMode } from "./state.js";
import { captureEvent } from "./telemetry.js";
import { CLI_VERSION } from "./version.js";

const program = new Command();

// ── Validated user identity (set by getBackendAndConfig) ─────────────────

let _validatedUserEmail: string | undefined;

// ── Helpers ──────────────────────────────────────────────────────────────

async function getBackendAndConfig(
	apiKey?: string,
	baseUrl?: string,
): Promise<{ backend: Backend; config: Mem0Config }> {
	const config = loadConfig();

	if (apiKey) config.platform.apiKey = apiKey;
	if (baseUrl) config.platform.baseUrl = baseUrl;

	if (!config.platform.apiKey) {
		printError(
			"No API key configured.",
			"Run 'mem0 init' or set MEM0_API_KEY environment variable.",
		);
		process.exit(1);
	}

	const backend = getBackend(config);

	// Validate the API key upfront with a fast timeout
	try {
		const pingData = (await Promise.race([
			backend.ping(),
			new Promise<never>((_, reject) =>
				setTimeout(() => reject(new Error("timeout")), 5000),
			),
		])) as Record<string, unknown>;

		const email = pingData?.user_email as string | undefined;
		if (email) {
			_validatedUserEmail = email;
			if (config.platform.userEmail !== email) {
				config.platform.userEmail = email;
				try {
					saveConfig(config);
				} catch {
					/* ignore */
				}
			}
		}
	} catch (e) {
		if (e instanceof AuthError) {
			printError(
				"Invalid or expired API key.",
				"Run 'mem0 init' or set MEM0_API_KEY environment variable.",
			);
			process.exit(1);
		}
		// Network error / timeout — warn but proceed
		printWarning(
			"Could not validate API key (network issue). Proceeding anyway.",
		);
	}

	return { backend, config };
}

async function getBackendOnly(
	apiKey?: string,
	baseUrl?: string,
): Promise<Backend> {
	return (await getBackendAndConfig(apiKey, baseUrl)).backend;
}

function checkAgentMode(): boolean {
	const rootOpts = program.opts();
	const isAgent = !!(rootOpts.json || rootOpts.agent);
	if (isAgent) setAgentMode(true);
	return isAgent;
}

/**
 * Resolve entity IDs: CLI flag > config default > undefined.
 *
 * If any explicit ID is provided, only use explicit IDs (don't mix
 * in defaults for other entity types which would over-filter).
 * If no explicit IDs, fall back to all configured defaults.
 */
function resolveIds(
	config: Mem0Config,
	opts: {
		userId?: string;
		agentId?: string;
		appId?: string;
		runId?: string;
	},
): { userId?: string; agentId?: string; appId?: string; runId?: string } {
	const hasExplicit = !!(
		opts.userId ||
		opts.agentId ||
		opts.appId ||
		opts.runId
	);
	if (hasExplicit) {
		return {
			userId: opts.userId || undefined,
			agentId: opts.agentId || undefined,
			appId: opts.appId || undefined,
			runId: opts.runId || undefined,
		};
	}
	return {
		userId: config.defaults.userId || undefined,
		agentId: config.defaults.agentId || undefined,
		appId: config.defaults.appId || undefined,
		runId: config.defaults.runId || undefined,
	};
}

// ── Main program ──────────────────────────────────────────────────────────

program
	.name("mem0")
	.description(
		`◆ Mem0 CLI v${CLI_VERSION} · Node.js SDK\n\nThe Memory Layer for AI Agents`,
	)
	.option("--version", "Show version and exit.")
	.on("option:version", () => {
		console.log(`  ${colors.brand("◆ Mem0")} CLI v${CLI_VERSION}`);
		process.exit(0);
	})
	.option("--json", "Output as JSON for agent/programmatic use.")
	.option(
		"--agent",
		"Output as JSON for agent/programmatic use. (alias: --json)",
	)
	.usage("<command> [options]")
	.helpOption("--help", "Show this message and exit.")
	.addHelpCommand(false)
	.configureHelp({ formatHelp: richFormatHelp });

// ── Telemetry hook ───────────────────────────────────────────────────────

program.hook("preAction", (_thisCommand, actionCommand) => {
	try {
		const commandName = actionCommand.name();
		const parentName = actionCommand.parent?.name();
		const fullCommand =
			parentName && parentName !== "mem0"
				? `${parentName}.${commandName}`
				: commandName;
		const isAgent = !!(program.opts().json || program.opts().agent);
		captureEvent(
			`cli.${fullCommand}`,
			{
				command: fullCommand,
				is_agent: isAgent,
			},
			_validatedUserEmail,
		);
	} catch {
		/* silently swallow */
	}
});

// ── Init ──────────────────────────────────────────────────────────────────

program
	.command("init")
	.description("Interactive setup wizard for mem0 CLI.")
	.option("--api-key <key>", "API key (skip prompt).")
	.option("-u, --user-id <id>", "Default user ID (skip prompt).")
	.option("--email <email>", "Login via email verification code.")
	.option(
		"--code <code>",
		"Verification code (use with --email for non-interactive login).",
	)
	.option("--force", "Overwrite existing config without confirmation.", false)
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 init\n  $ mem0 init --api-key m0-xxx --user-id alice\n  $ mem0 init --email you@example.com\n  $ mem0 init --email you@example.com --code 123456",
	)
	.action(async (opts) => {
		const { runInit } = await import("./commands/init.js");
		await runInit({
			apiKey: opts.apiKey,
			userId: opts.userId,
			email: opts.email,
			code: opts.code,
			force: opts.force,
		});
	});

// ── Memory: add ───────────────────────────────────────────────────────────

program
	.command("add [text]")
	.description("Add a memory from text, messages, file, or stdin.")
	.option("-u, --user-id <id>", "Scope to user.")
	.option("--agent-id <id>", "Scope to agent.")
	.option("--app-id <id>", "Scope to app.")
	.option("--run-id <id>", "Scope to run.")
	.option("--messages <json>", "Conversation messages as JSON.")
	.option("-f, --file <path>", "Read messages from JSON file.")
	.option("-m, --metadata <json>", "Custom metadata as JSON.")
	.option("--immutable", "Prevent future updates.", false)
	.option("--no-infer", "Skip inference, store raw.")
	.option("--expires <date>", "Expiration date (YYYY-MM-DD).")
	.option("--categories <value>", "Categories (JSON array or comma-separated).")
	.option("-o, --output <format>", "Output format: text, json, quiet.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		'\nExamples:\n  $ mem0 add "I prefer dark mode" --user-id alice\n  $ echo "text" | mem0 add -u alice\n  $ mem0 add --file msgs.json -u alice -o json',
	)
	.action(async (text, opts) => {
		const { cmdAdd } = await import("./commands/memory.js");
		const isAgent = checkAgentMode();
		const { backend, config } = await getBackendAndConfig(
			opts.apiKey,
			opts.baseUrl,
		);
		const ids = resolveIds(config, opts);
		const output = isAgent ? "agent" : opts.output;
		await cmdAdd(backend, text, { ...ids, ...opts, output });
	});

// ── Memory: search ────────────────────────────────────────────────────────

program
	.command("search [query]")
	.description(
		"Query your memory store — semantic, keyword, or hybrid retrieval.",
	)
	.option("-u, --user-id <id>", "Filter by user.")
	.option("--agent-id <id>", "Filter by agent.")
	.option("--app-id <id>", "Filter by app.")
	.option("--run-id <id>", "Filter by run.")
	.option(
		"-k, --top-k <n>",
		"Number of results.",
		(v) => Number.parseInt(v),
		10,
	)
	.option(
		"--threshold <n>",
		"Minimum similarity score.",
		(v) => Number.parseFloat(v),
		0.3,
	)
	.option("--rerank", "Enable reranking (Platform only).", false)
	.option("--keyword", "Use keyword search.", false)
	.option("--filter <json>", "Advanced filter expression (JSON).")
	.option("--fields <list>", "Specific fields to return (comma-separated).")
	.option("-o, --output <format>", "Output: text, json, table.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		'\nExamples:\n  $ mem0 search "preferences" --user-id alice\n  $ mem0 search "tools" -u alice -o json -k 5\n  $ echo "preferences" | mem0 search -u alice',
	)
	.action(async (query, opts) => {
		let resolvedQuery = query;
		if (!resolvedQuery && !process.stdin.isTTY) {
			resolvedQuery = fs.readFileSync(0, "utf-8").trim();
		}
		if (!resolvedQuery) {
			printError("No query provided. Pass a query argument or pipe via stdin.");
			process.exit(1);
		}
		const { cmdSearch } = await import("./commands/memory.js");
		const isAgent = checkAgentMode();
		const { backend, config } = await getBackendAndConfig(
			opts.apiKey,
			opts.baseUrl,
		);
		const ids = resolveIds(config, opts);
		const output = isAgent ? "agent" : opts.output;
		await cmdSearch(backend, resolvedQuery, {
			...ids,
			topK: opts.topK,
			threshold: opts.threshold,
			rerank: opts.rerank,
			keyword: opts.keyword,
			filterJson: opts.filter,
			fields: opts.fields,
			output,
		});
	});

// ── Memory: get ───────────────────────────────────────────────────────────

program
	.command("get <memoryId>")
	.description("Get a specific memory by ID.")
	.option("-o, --output <format>", "Output: text, json.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 get abc-123-def-456\n  $ mem0 get abc-123-def-456 -o json",
	)
	.action(async (memoryId, opts) => {
		const { cmdGet } = await import("./commands/memory.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdGet(backend, memoryId, { output });
	});

// ── Memory: list ──────────────────────────────────────────────────────────

program
	.command("list")
	.description("List memories with optional filters.")
	.option("-u, --user-id <id>", "Filter by user.")
	.option("--agent-id <id>", "Filter by agent.")
	.option("--app-id <id>", "Filter by app.")
	.option("--run-id <id>", "Filter by run.")
	.option("--page <n>", "Page number.", (v) => Number.parseInt(v), 1)
	.option(
		"--page-size <n>",
		"Results per page.",
		(v) => Number.parseInt(v),
		100,
	)
	.option("--category <name>", "Filter by category.")
	.option("--after <date>", "Created after (YYYY-MM-DD).")
	.option("--before <date>", "Created before (YYYY-MM-DD).")
	.option("-o, --output <format>", "Output: text, json, table.", "table")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 list -u alice\n  $ mem0 list --category prefs --after 2024-01-01 -o json",
	)
	.action(async (opts) => {
		const { cmdList } = await import("./commands/memory.js");
		const isAgent = checkAgentMode();
		const { backend, config } = await getBackendAndConfig(
			opts.apiKey,
			opts.baseUrl,
		);
		const ids = resolveIds(config, opts);
		const output = isAgent ? "agent" : opts.output;
		await cmdList(backend, {
			...ids,
			page: opts.page,
			pageSize: opts.pageSize,
			category: opts.category,
			after: opts.after,
			before: opts.before,
			output,
		});
	});

// ── Memory: update ────────────────────────────────────────────────────────

program
	.command("update <memoryId> [text]")
	.description("Update a memory's text or metadata.")
	.option("-m, --metadata <json>", "Update metadata (JSON).")
	.option("-o, --output <format>", "Output: text, json, quiet.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		`\nExamples:\n  $ mem0 update abc-123 "new text"\n  $ mem0 update abc-123 --metadata '{"key":"val"}'\n  $ echo "new text" | mem0 update abc-123`,
	)
	.action(async (memoryId, text, opts) => {
		let resolvedText = text;
		if (!resolvedText && !opts.metadata && !process.stdin.isTTY) {
			resolvedText = fs.readFileSync(0, "utf-8").trim();
		}
		const { cmdUpdate } = await import("./commands/memory.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdUpdate(backend, memoryId, resolvedText, {
			metadata: opts.metadata,
			output,
		});
	});

// ── Memory: delete (consolidated) ─────────────────────────────────────────

program
	.command("delete [memoryId]")
	.description("Delete a memory, all memories matching a scope, or an entity.")
	.option("--all", "Delete all memories matching scope filters.", false)
	.option(
		"--entity",
		"Delete the entity itself and all its memories (cascade).",
		false,
	)
	.option("--project", "With --all: delete ALL memories project-wide.", false)
	.option("--dry-run", "Show what would be deleted without deleting.", false)
	.option("--force", "Skip confirmation.", false)
	.option("-u, --user-id <id>", "Scope to user.")
	.option("--agent-id <id>", "Scope to agent.")
	.option("--app-id <id>", "Scope to app.")
	.option("--run-id <id>", "Scope to run.")
	.option("-o, --output <format>", "Output: text, json, quiet.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		[
			"\nExamples:",
			"  $ mem0 delete abc-123-def-456              # single memory",
			"  $ mem0 delete --all -u alice --force        # all memories for user",
			"  $ mem0 delete --all --project --force       # project-wide wipe",
			"  $ mem0 delete --entity -u alice --force     # entity + all its memories",
		].join("\n"),
	)
	.action(async (memoryId, opts) => {
		const isAgent = checkAgentMode();
		const output = isAgent ? "agent" : opts.output;
		// ── Mutual-exclusion checks ──
		if (memoryId && opts.all) {
			printError("Cannot combine <memoryId> with --all. Use one or the other.");
			process.exit(1);
		}
		if (memoryId && opts.entity) {
			printError(
				"Cannot combine <memoryId> with --entity. Use one or the other.",
			);
			process.exit(1);
		}
		if (opts.all && opts.entity) {
			printError("Cannot combine --all with --entity. Use one or the other.");
			process.exit(1);
		}
		if (!memoryId && !opts.all && !opts.entity) {
			printError(
				"Specify a memory ID, --all, or --entity.\n" +
					"  mem0 delete <id>              Delete a single memory\n" +
					"  mem0 delete --all [scope]     Delete all memories matching scope\n" +
					"  mem0 delete --entity [scope]  Delete an entity and all its memories",
			);
			process.exit(1);
		}

		// ── Dispatch: single memory ──
		if (memoryId) {
			const { cmdDelete } = await import("./commands/memory.js");
			const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
			await cmdDelete(backend, memoryId, {
				output,
				dryRun: opts.dryRun,
				force: opts.force,
			});
			return;
		}

		// ── Dispatch: --all ──
		if (opts.all) {
			const { cmdDeleteAll } = await import("./commands/memory.js");
			const { backend, config } = await getBackendAndConfig(
				opts.apiKey,
				opts.baseUrl,
			);
			const ids = opts.project
				? {
						userId: undefined,
						agentId: undefined,
						appId: undefined,
						runId: undefined,
					}
				: resolveIds(config, opts);
			await cmdDeleteAll(backend, {
				force: opts.force,
				dryRun: opts.dryRun,
				all: opts.project,
				...ids,
				output,
			});
			return;
		}

		// ── Dispatch: --entity ──
		if (opts.entity) {
			const { cmdEntitiesDelete } = await import("./commands/entities.js");
			const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
			await cmdEntitiesDelete(backend, { ...opts, output });
			return;
		}
	});

// ── Config subcommands ────────────────────────────────────────────────────

const configCmd = program
	.command("config")
	.description("Manage mem0 configuration.")
	.addHelpCommand(false);

configCmd
	.command("show")
	.description("Display current configuration (secrets redacted).")
	.option("-o, --output <format>", "Output: text, json.", "text")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 config show\n  $ mem0 config show -o json",
	)
	.action(async (opts) => {
		const { cmdConfigShow } = await import("./commands/config.js");
		const isAgent = checkAgentMode();
		const output = isAgent ? "agent" : opts.output;
		cmdConfigShow({ output });
	});

configCmd
	.command("get <key>")
	.description("Get a configuration value.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 config get platform.api_key\n  $ mem0 config get defaults.user_id",
	)
	.action(async (key) => {
		const { cmdConfigGet } = await import("./commands/config.js");
		checkAgentMode();
		cmdConfigGet(key);
	});

configCmd
	.command("set <key> <value>")
	.description("Set a configuration value.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 config set defaults.user_id alice\n  $ mem0 config set platform.base_url https://api.mem0.ai",
	)
	.action(async (key, value) => {
		const { cmdConfigSet } = await import("./commands/config.js");
		checkAgentMode();
		cmdConfigSet(key, value);
	});

// ── Entity subcommand group ───────────────────────────────────────────────

const entityCmd = program
	.command("entity")
	.description("Manage entities.")
	.addHelpCommand(false)
	.configureHelp({ formatHelp: richFormatHelp });

entityCmd
	.command("list <entityType>")
	.description("List all entities of a given type.")
	.option("-o, --output <format>", "Output: table, json.", "table")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 entity list users\n  $ mem0 entity list agents -o json",
	)
	.action(async (entityType, opts) => {
		const { cmdEntitiesList } = await import("./commands/entities.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdEntitiesList(backend, entityType, { output });
	});

entityCmd
	.command("delete")
	.description("Delete an entity and ALL its memories (cascade).")
	.option("--dry-run", "Show what would be deleted without deleting.", false)
	.option("-u, --user-id <id>", "Scope to user.")
	.option("--agent-id <id>", "Scope to agent.")
	.option("--app-id <id>", "Scope to app.")
	.option("--run-id <id>", "Scope to run.")
	.option("--force", "Skip confirmation.", false)
	.option("-o, --output <format>", "Output: text, json, quiet.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 entity delete --user-id alice --force\n  $ mem0 entity delete --user-id alice --dry-run",
	)
	.action(async (opts) => {
		const { cmdEntitiesDelete } = await import("./commands/entities.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdEntitiesDelete(backend, { ...opts, output });
	});

// ── Event subcommands ─────────────────────────────────────────────────────

const eventCmd = program
	.command("event")
	.description("Inspect background processing events.")
	.addHelpCommand(false)
	.configureHelp({ formatHelp: richFormatHelp });

eventCmd
	.command("list")
	.description("List recent background processing events.")
	.option("-o, --output <format>", "Output: table, json.", "table")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 event list\n  $ mem0 event list -o json",
	)
	.action(async (opts) => {
		const { cmdEventList } = await import("./commands/events.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdEventList(backend, { output });
	});

eventCmd
	.command("status <eventId>")
	.description("Check the status of a specific background event.")
	.option("-o, --output <format>", "Output: text, json.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 event status <event-id>\n  $ mem0 event status <event-id> -o json",
	)
	.action(async (eventId, opts) => {
		const { cmdEventStatus } = await import("./commands/events.js");
		const isAgent = checkAgentMode();
		const backend = await getBackendOnly(opts.apiKey, opts.baseUrl);
		const output = isAgent ? "agent" : opts.output;
		await cmdEventStatus(backend, eventId, { output });
	});

// ── Utility commands ──────────────────────────────────────────────────────

program
	.command("status")
	.description("Check connectivity and authentication.")
	.option("-o, --output <format>", "Output: text, json.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText("after", "\nExamples:\n  $ mem0 status\n  $ mem0 status -o json")
	.action(async (opts) => {
		const { cmdStatus } = await import("./commands/utils.js");
		const isAgent = checkAgentMode();
		const { backend, config } = await getBackendAndConfig(
			opts.apiKey,
			opts.baseUrl,
		);
		const output = isAgent ? "agent" : opts.output;
		await cmdStatus(backend, {
			userId: config.defaults.userId || undefined,
			agentId: config.defaults.agentId || undefined,
			output,
		});
	});

program
	.command("import <filePath>")
	.description("Import memories from a JSON file.")
	.option("-u, --user-id <id>", "Override user ID.")
	.option("--agent-id <id>", "Override agent ID.")
	.option("-o, --output <format>", "Output: text, json.", "text")
	.option("--api-key <key>", "Override API key.")
	.option("--base-url <url>", "Override API base URL.")
	.addHelpText(
		"after",
		"\nExamples:\n  $ mem0 import data.json --user-id alice\n  $ mem0 import data.json -u alice -o json",
	)
	.action(async (filePath, opts) => {
		const { cmdImport } = await import("./commands/utils.js");
		const isAgent = checkAgentMode();
		const { backend, config } = await getBackendAndConfig(
			opts.apiKey,
			opts.baseUrl,
		);
		const ids = resolveIds(config, opts);
		const output = isAgent ? "agent" : opts.output;
		await cmdImport(backend, filePath, {
			userId: ids.userId,
			agentId: ids.agentId,
			output,
		});
	});

// ── Help (machine-readable) ──────────────────────────────────────────────

program
	.command("help")
	.description(
		"Show help. Use --json for machine-readable output (for LLM agents).",
	)
	.option("--json", "Output machine-readable JSON for LLM agents.", false)
	.addHelpText("after", "\nExamples:\n  $ mem0 help\n  $ mem0 help --json")
	.action((opts) => {
		// opts.json is set when `mem0 help --json` is used (subcommand flag).
		// program.opts().json is set when the root --json global flag was used first.
		if (opts.json || program.opts().json) {
			// Load spec from parent directory
			const __dirname = path.dirname(fileURLToPath(import.meta.url));
			const specPath = path.join(__dirname, "..", "..", "cli-spec.json");
			if (fs.existsSync(specPath)) {
				const spec = JSON.parse(fs.readFileSync(specPath, "utf-8"));
				console.log(JSON.stringify(spec, null, 2));
			} else {
				console.log(
					JSON.stringify(
						{
							name: "mem0",
							version: CLI_VERSION,
							description: "The Memory Layer for AI Agents",
						},
						null,
						2,
					),
				);
			}
		} else {
			const { brand: b } = colors;
			console.log(
				`${b("◆ Mem0 CLI")} v${CLI_VERSION} · Node.js SDK\n  The Memory Layer for AI Agents\n`,
			);
			console.log("Usage: mem0 <command> [OPTIONS]\n");
			console.log("Commands:");
			console.log(
				"  add              Add a memory from text, messages, file, or stdin",
			);
			console.log(
				"  search           Query your memory store (semantic, keyword, hybrid)",
			);
			console.log("  get              Get a specific memory by ID");
			console.log("  list             List memories with optional filters");
			console.log("  update           Update a memory's text or metadata");
			console.log(
				"  delete           Delete a memory, all memories, or an entity",
			);
			console.log("  import           Import memories from a JSON file");
			console.log("  config           Manage configuration (show, get, set)");
			console.log("  entity           Manage entities (list, delete)");
			console.log(
				"  event            Inspect background events (list, status)",
			);
			console.log("  init             Interactive setup wizard");
			console.log("  status           Check connectivity and authentication");
			console.log();
			console.log("  mem0 <command> --help    Get help for a command");
			console.log(
				"  mem0 help --json         Machine-readable help (for LLM agents)",
			);
			console.log();
		}
	});

// ── Entrypoint ────────────────────────────────────────────────────────────

program.parse();
