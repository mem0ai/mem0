import { createRequire } from "node:module";
import { defineConfig } from "vitest/config";

const _require = createRequire(import.meta.url);
const pkg = _require("./package.json") as { version: string };

export default defineConfig({
	define: {
		__CLI_VERSION__: JSON.stringify(pkg.version),
	},
	test: {
		// Integration tests spawn the CLI via `npx tsx` (15s subprocess
		// timeout); the first spawn in a file pays a cold-start cost that can
		// exceed vitest's 5s default on CI runners.
		testTimeout: 30_000,
	},
});
