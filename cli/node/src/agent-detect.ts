/**
 * Detect which AI agent is invoking the CLI via environment variables.
 *
 * Used by `mem0 init` to:
 *   1. Decide whether to auto-bootstrap an Agent Mode key (positive agent signal).
 *   2. Tag the `agent_caller` PostHog property on the cli.init event.
 *
 * Returns a canonical short name or null when no agent is detected.
 */

const AGENT_CALLER_ENV: ReadonlyArray<readonly [string, readonly string[]]> = [
	["claude-code", ["CLAUDECODE", "CLAUDE_CODE"]],
	["cursor", ["CURSOR_AGENT", "CURSOR_SESSION_ID"]],
	["codex", ["CODEX_CLI", "OPENAI_CODEX"]],
	["cline", ["CLINE_AGENT", "CLINE"]],
	["continue", ["CONTINUE_AGENT", "CONTINUE_SESSION"]],
	["aider", ["AIDER_SESSION"]],
	["goose", ["GOOSE_AGENT"]],
	["windsurf", ["WINDSURF_AGENT"]],
] as const;

export function detectAgentCaller(): string | null {
	for (const [name, envVars] of AGENT_CALLER_ENV) {
		if (envVars.some((v) => process.env[v])) {
			return name;
		}
	}
	return null;
}
