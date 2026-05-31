/**
 * Agent mode state — set by the root program option handler,
 * read by commands and branding functions.
 */

let _agentMode = false;
let _currentCommand = "";
let _pendingNotice = "";

export function isAgentMode(): boolean {
	return _agentMode;
}

export function setAgentMode(val: boolean): void {
	_agentMode = val;
}

export function getCurrentCommand(): string {
	return _currentCommand;
}

export function setCurrentCommand(name: string): void {
	_currentCommand = name;
}

/**
 * Stash a Mem0 backend notice (Agent Mode unclaimed reminder) for end-of-
 * command surfacing. Called from the platform backend after each response so
 * the notice prints once per command regardless of how many sub-requests
 * fired. Last-write-wins is fine — the message text is identical.
 */
export function captureNotice(notice: string | null | undefined): void {
	if (notice) _pendingNotice = notice;
}

export function takeNotice(): string {
	const msg = _pendingNotice;
	_pendingNotice = "";
	return msg;
}
