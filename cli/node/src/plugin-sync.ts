/**
 * Sync the active Mem0 API key into other ecosystem touchpoints.
 *
 * Why: the CLI canonical state is ~/.mem0/config.json. MCP servers
 * (Claude Code plugin, Codex plugin) read MEM0_API_KEY from env or
 * their own config files. Without a sync, agent-mode bootstrap mints a
 * new key into config.json but the plugin's MCP keeps using the old
 * key from env — silent surprise.
 *
 * Design:
 *  - Update ONLY entries that already exist; never create new ones
 *  - Preserve surrounding content, formatting, other keys
 *  - Atomic writes (tmp + rename) so a crash mid-write doesn't corrupt
 *  - Idempotent — re-running with the same key is a no-op
 *
 * Targets:
 *  - ~/.claude/settings.json::env::MEM0_API_KEY (Claude Code env injection)
 *  - ~/.zshrc / ~/.bashrc `export MEM0_API_KEY="..."` lines
 *
 * Out of scope: Codex / Cursor MCP configs and the plugin's own
 * <plugin-dir>/.api_key file (plugin-managed, different schema).
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const CLAUDE_SETTINGS = path.join(os.homedir(), ".claude", "settings.json");
const SHELL_RCS = [
	path.join(os.homedir(), ".zshrc"),
	path.join(os.homedir(), ".bashrc"),
	path.join(os.homedir(), ".bash_profile"),
];

// Use [ \t]* (not \s*) so a trailing newline at end-of-file is preserved
// when the MEM0_API_KEY export is the last line of the rc file.
const RC_LINE_RE =
	/^([ \t]*export[ \t]+MEM0_API_KEY[ \t]*=[ \t]*)(["']?)([^"'\n]*)(["']?)[ \t]*$/m;

export function syncApiKey(apiKey: string): string[] {
	if (!apiKey) return [];
	const updated: string[] = [];
	if (updateClaudeSettings(CLAUDE_SETTINGS, apiKey)) {
		updated.push(CLAUDE_SETTINGS);
	}
	for (const rc of SHELL_RCS) {
		if (updateShellRc(rc, apiKey)) updated.push(rc);
	}
	return updated;
}

/** @internal — exported for unit tests; consumers should use {@link syncApiKey}. */
export function updateClaudeSettings(
	filePath: string,
	apiKey: string,
): boolean {
	if (!fs.existsSync(filePath)) return false;
	let raw: string;
	let data: Record<string, unknown>;
	try {
		raw = fs.readFileSync(filePath, "utf-8");
		data = JSON.parse(raw);
	} catch {
		return false;
	}
	const env = data.env;
	if (!env || typeof env !== "object" || !("MEM0_API_KEY" in env)) {
		return false; // no existing entry — don't create one
	}
	const envObj = env as Record<string, string>;
	if (envObj.MEM0_API_KEY === apiKey) return false; // already in sync
	envObj.MEM0_API_KEY = apiKey;
	atomicWriteText(filePath, `${JSON.stringify(data, null, 2)}\n`);
	return true;
}

/** @internal — exported for unit tests; consumers should use {@link syncApiKey}. */
export function updateShellRc(filePath: string, apiKey: string): boolean {
	if (!fs.existsSync(filePath)) return false;
	let text: string;
	try {
		text = fs.readFileSync(filePath, "utf-8");
	} catch {
		return false;
	}
	const match = text.match(RC_LINE_RE);
	if (!match) return false; // no existing line
	if (match[3] === apiKey) return false;
	const newText = text.replace(
		RC_LINE_RE,
		(_full, prefix) => `${prefix}"${apiKey}"`,
	);
	atomicWriteText(filePath, newText);
	return true;
}

function atomicWriteText(filePath: string, content: string): void {
	const dir = path.dirname(filePath);
	const tmp = path.join(dir, `.${path.basename(filePath)}.${process.pid}.tmp`);
	try {
		fs.writeFileSync(tmp, content, "utf-8");
		// Preserve permissions if original existed.
		if (fs.existsSync(filePath)) {
			try {
				const mode = fs.statSync(filePath).mode & 0o777;
				fs.chmodSync(tmp, mode);
			} catch {
				/* best-effort */
			}
		}
		fs.renameSync(tmp, filePath);
	} catch (err) {
		try {
			fs.unlinkSync(tmp);
		} catch {
			/* ignore */
		}
		throw err;
	}
}
