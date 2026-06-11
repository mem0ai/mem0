/**
 * `mem0 whoami` — print the active agent's default_user_id (AGENTRUSH identifier).
 * Reads from local config; no network call.
 */

import { colors, printError, printInfo } from "../branding.js";
import { loadConfig } from "../config.js";

export async function cmdWhoami(): Promise<void> {
	const config = loadConfig();
	const sessionId = config.platform?.defaultUserId;
	if (!sessionId) {
		printError("No default_user_id found. Run `mem0 init --agent` first.");
		process.exit(1);
	}
	console.log(`Your AGENTRUSH identifier:  ${colors.brand(sessionId)}`);
	printInfo("Find your row at https://mem0.ai/agentrush");
}
