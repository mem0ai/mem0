/**
 * Agent mode state — set by the root program option handler,
 * read by commands and branding functions.
 */

let _agentMode = false;
let _currentCommand = "";

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
