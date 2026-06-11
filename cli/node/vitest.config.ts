import { createRequire } from "node:module";
import { defineConfig } from "vitest/config";

const _require = createRequire(import.meta.url);
const pkg = _require("./package.json") as { version: string };

export default defineConfig({
	define: {
		__CLI_VERSION__: JSON.stringify(pkg.version),
	},
});
