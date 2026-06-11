import { createRequire } from "node:module";

// __CLI_VERSION__ is replaced at build time by tsup (see tsup.config.ts).
// When running via tsx in dev/test mode, fall back to reading package.json.
// typeof is safe to use on undeclared identifiers — it returns 'undefined' without throwing.
export const CLI_VERSION: string =
	typeof __CLI_VERSION__ !== "undefined"
		? (__CLI_VERSION__ as string)
		: (createRequire(import.meta.url)("../package.json") as { version: string })
				.version;
