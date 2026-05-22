/**
 * Detect whether the CLI is being invoked from inside an AI-agent context.
 *
 * Used by `mem0 init` to auto-enter Agent Mode (Rule 3 bootstrap) when an
 * agent runtime env var is present. The return value is a context **trigger
 * only** — the canonical agent identity is self-declared by the agent via
 * `--agent-caller <name>` (Proof Editor-style) and never sniffed from env
 * vars to fill the `agent_caller` field on the APIKey row.
 *
 * Returns a short name or null. Honest reporting depends on `--agent-caller`;
 * this list is just enough to enable the zero-friction auto-bootstrap UX.
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
