/**
 * Rich-style help formatter for Commander.js that matches the Python CLI's
 * Typer + Rich output (rounded box panels, brand purple, grouped options).
 */

import chalk from "chalk";
import type { Argument, Command, Help, Option } from "commander";
// Colors imported from chalk directly to match Typer/Rich defaults

// ── Colors (matching Typer/Rich defaults) ────────────────────────────────

const cyanBold = chalk.cyan.bold; // option flags, command names
const greenBold = chalk.green.bold; // switch flags (boolean --force etc)
const yellowBold = chalk.yellow.bold; // metavar <value>
const yellow = chalk.yellow; // "Usage:" label
const bold = chalk.bold; // command name in usage
const dim = chalk.dim; // defaults, descriptions
const dimBorder = chalk.dim; // panel borders

// ── Strip ANSI ───────────────────────────────────────────────────────────

// biome-ignore lint/suspicious/noControlCharactersInRegex: ANSI escape sequence is intentional
const ANSI_RE = /\x1b\[[0-9;]*m/g;

function stripAnsi(str: string): number {
	return str.replace(ANSI_RE, "").length;
}

// ── Command display order (matches Python CLI) ──────────────────────────

/** Commands grouped into panels, matching Python CLI's rich_help_panel. */
const COMMAND_GROUPS: { panel: string; commands: string[] }[] = [
	{
		panel: "Memory",
		commands: ["add", "search", "get", "list", "update", "delete"],
	},
	{
		panel: "Management",
		commands: ["init", "status", "import", "help", "entity", "event", "config"],
	},
];

/** Flat order derived from COMMAND_GROUPS. */
const COMMAND_ORDER: string[] = COMMAND_GROUPS.flatMap((g) => g.commands);

// ── Option-to-panel mapping (derived from Python's rich_help_panel) ─────

const OPTION_PANELS: Record<string, Record<string, string>> = {
	add: {
		"--user-id": "Scope",
		"--agent-id": "Scope",
		"--app-id": "Scope",
		"--run-id": "Scope",
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	search: {
		"--user-id": "Scope",
		"--agent-id": "Scope",
		"--app-id": "Scope",
		"--run-id": "Scope",
		"--top-k": "Search",
		"--threshold": "Search",
		"--rerank": "Search",
		"--keyword": "Search",
		"--filter": "Search",
		"--fields": "Search",
		"--graph": "Search",
		"--no-graph": "Search",
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	get: {
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	list: {
		"--user-id": "Scope",
		"--agent-id": "Scope",
		"--app-id": "Scope",
		"--run-id": "Scope",
		"--page": "Pagination",
		"--page-size": "Pagination",
		"--category": "Filters",
		"--after": "Filters",
		"--before": "Filters",
		"--graph": "Filters",
		"--no-graph": "Filters",
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	update: {
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	delete: {
		"--user-id": "Scope",
		"--agent-id": "Scope",
		"--app-id": "Scope",
		"--run-id": "Scope",
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	status: {
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
	import: {
		"--user-id": "Scope",
		"--agent-id": "Scope",
		"--output": "Output",
		"--api-key": "Connection",
		"--base-url": "Connection",
	},
};

const PANEL_ORDER: string[] = [
	"Scope",
	"Search",
	"Pagination",
	"Filters",
	"Output",
	"Connection",
];

// ── Panel rendering ─────────────────────────────────────────────────────

/**
 * Render a Rich-style ROUNDED box panel.
 *
 * ```
 * ╭─ Title ────────────────────────╮
 * │ row content padded             │
 * ╰────────────────────────────────╯
 * ```
 */
function renderPanel(title: string, rows: string[], width: number): string {
	if (rows.length === 0) return "";

	// Inner width is total width minus the two border chars
	const inner = width - 2;

	// Top border: ╭─ Title ─...─╮
	const titleStr = ` ${title} `;
	const fillLen = Math.max(0, inner - 1 - titleStr.length);
	const topLine =
		dimBorder("╭─") +
		dimBorder(titleStr) +
		dimBorder("─".repeat(fillLen)) +
		dimBorder("╮");

	// Bottom border: ╰─...─╯
	const bottomLine =
		dimBorder("╰") + dimBorder("─".repeat(inner)) + dimBorder("╯");

	// Content rows
	const contentLines = rows.map((row) => {
		const visLen = stripAnsi(row);
		const pad = Math.max(0, inner - 1 - visLen);
		return `${dimBorder("│")} ${row}${" ".repeat(pad)}${dimBorder("│")}`;
	});

	return [topLine, ...contentLines, bottomLine].join("\n");
}

// ── Format an option term (short + long) ────────────────────────────────

function formatOptionTerm(opt: Option): string {
	const parts: string[] = [];
	if (opt.short) parts.push(opt.short);
	if (opt.long) parts.push(opt.long);
	let term = parts.join(", ");

	// Append value placeholder for non-boolean options
	if (opt.flags) {
		const match = opt.flags.match(/<[^>]+>|\[[^\]]+\]/);
		if (match) {
			term += ` ${match[0]}`;
		}
	}
	return term;
}

// ── Get the long flag name for panel lookup ─────────────────────────────

function getLongFlag(opt: Option): string {
	if (opt.long) return opt.long;
	return opt.short || "";
}

// ── Format a default value ──────────────────────────────────────────────

function formatDefault(opt: Option): string {
	if (opt.defaultValue !== undefined && opt.defaultValue !== false) {
		return dim(` [default: ${opt.defaultValue}]`);
	}
	return "";
}

// ── The main help formatter ─────────────────────────────────────────────

export function richFormatHelp(cmd: Command, helper: Help): string {
	const width = process.stdout.columns || 80;
	const lines: string[] = [];

	const isRoot = !cmd.parent;

	// ── Usage line ──
	const usage = helper.commandUsage(cmd);
	lines.push("");
	if (isRoot) {
		// Root: "Usage: mem0 <command> [options]" — <command> yellow, [options] bold
		lines.push(
			` ${yellow("Usage:")} ${bold(cmd.name())} ${yellow("<command>")} ${bold("[options]")}`,
		);
	} else {
		// Subcommands: split into command path (bold) and args (yellow)
		const usageParts = usage.split(" ");
		const cmdPath: string[] = [];
		const argParts: string[] = [];
		let pastCmd = false;
		for (const part of usageParts) {
			if (!pastCmd && !part.startsWith("[") && !part.startsWith("<")) {
				cmdPath.push(part);
			} else {
				pastCmd = true;
				argParts.push(part);
			}
		}
		lines.push(
			` ${yellow("Usage:")} ${bold(cmdPath.join(" "))} ${yellow(argParts.join(" "))}`,
		);
	}
	lines.push("");

	// ── Description ──
	const desc = helper.commandDescription(cmd);
	if (desc) {
		// Split multi-line descriptions (e.g., title + tagline)
		const descLines = desc.split("\n");
		for (let i = 0; i < descLines.length; i++) {
			const dLine = descLines[i];
			// First line is the title, subsequent non-empty lines are tagline (dimmed)
			if (i === 0 || dLine.trim() === "") {
				lines.push(` ${dLine}`);
			} else {
				lines.push(` ${dim(dLine)}`);
			}
		}
		lines.push("");
	}

	// ── Arguments panel (subcommands only) ──
	if (!isRoot) {
		const visibleArgs = helper.visibleArguments(cmd);
		if (visibleArgs.length > 0) {
			const maxLen = Math.max(
				...visibleArgs.map((a: Argument) => a.name().length),
			);
			const argRows = visibleArgs.map((a: Argument) => {
				const name = cyanBold(a.name().padEnd(maxLen));
				const description = helper.argumentDescription(a);
				return ` ${name}  ${description}`;
			});
			const panel = renderPanel("Arguments", argRows, width);
			if (panel) lines.push(panel);
		}
	}

	// ── Collect options (grouped into panels for subcommands) ──
	const visibleOpts = helper.visibleOptions(cmd);
	const cmdName = cmd.name();
	const panelMap =
		!isRoot && OPTION_PANELS[cmdName] ? OPTION_PANELS[cmdName] : {};

	const grouped: Record<string, Option[]> = { Options: [] };
	for (const panelName of PANEL_ORDER) {
		grouped[panelName] = [];
	}

	for (const opt of visibleOpts) {
		const flag = getLongFlag(opt);
		const panel = panelMap[flag];
		if (panel && PANEL_ORDER.includes(panel)) {
			grouped[panel].push(opt);
		} else {
			grouped.Options.push(opt);
		}
	}

	// ── Collect commands ──
	const visibleCmds = helper.visibleCommands(cmd);

	if (isRoot) {
		// ROOT: Options first, then command groups (matches Python/Typer ordering)
		if (grouped.Options.length > 0) {
			const optRows = formatOptionRows(grouped.Options);
			const panel = renderPanel("Options", optRows, width);
			if (panel) lines.push(panel);
		}
		if (visibleCmds.length > 0) {
			const cmdMap = new Map(visibleCmds.map((c) => [c.name(), c]));
			for (const group of COMMAND_GROUPS) {
				const groupCmds = group.commands
					.map((name) => cmdMap.get(name))
					.filter((c): c is Command => c !== undefined);
				if (groupCmds.length === 0) continue;
				const maxLen = Math.max(...groupCmds.map((c) => c.name().length));
				const cmdRows = groupCmds.map((c) => {
					const name = cyanBold(c.name().padEnd(maxLen));
					const description = helper.subcommandDescription(c);
					return ` ${name}  ${description}`;
				});
				const panel = renderPanel(group.panel, cmdRows, width);
				if (panel) lines.push(panel);
			}
		}
	} else {
		// SUBCOMMANDS: Options/panels first, then sub-subcommands
		const panelSequence = ["Options", ...PANEL_ORDER];
		for (const panelName of panelSequence) {
			const opts = grouped[panelName];
			if (opts && opts.length > 0) {
				const optRows = formatOptionRows(opts);
				const panel = renderPanel(panelName, optRows, width);
				if (panel) lines.push(panel);
			}
		}
		// Sub-subcommands (e.g., config show/get/set, entity list/delete)
		if (visibleCmds.length > 0) {
			const maxLen = Math.max(...visibleCmds.map((c) => c.name().length));
			const cmdRows = visibleCmds.map((c) => {
				const name = cyanBold(c.name().padEnd(maxLen));
				const description = helper.subcommandDescription(c);
				return ` ${name}  ${description}`;
			});
			const panel = renderPanel("Commands", cmdRows, width);
			if (panel) lines.push(panel);
		}
	}

	lines.push("");
	return lines.join("\n");
}

// ── Format option rows with aligned columns ─────────────────────────────

function formatOptionRows(opts: Option[]): string[] {
	const terms = opts.map((o) => formatOptionTerm(o));
	const maxTermLen = Math.max(...terms.map((t) => t.length));

	return opts.map((opt, i) => {
		const term = cyanBold(terms[i].padEnd(maxTermLen));
		const desc = opt.description || "";
		const def = formatDefault(opt);
		return ` ${term}  ${desc}${def}`;
	});
}

// ── Sort commands by COMMAND_ORDER ──────────────────────────────────────

function sortCommands(cmds: Command[]): Command[] {
	return [...cmds].sort((a, b) => {
		const ai = COMMAND_ORDER.indexOf(a.name());
		const bi = COMMAND_ORDER.indexOf(b.name());
		// Unknown commands go to end, preserving original order
		const aIdx = ai === -1 ? COMMAND_ORDER.length : ai;
		const bIdx = bi === -1 ? COMMAND_ORDER.length : bi;
		return aIdx - bIdx;
	});
}
