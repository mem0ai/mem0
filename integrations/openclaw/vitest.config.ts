import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import pkg from "./package.json";

export default defineConfig({
  define: {
    __OPENCLAW_PLUGIN_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    alias: {
      // OpenClaw SDK modules are resolved from the gateway at runtime.
      // During unit tests we provide lightweight stubs.
      // fileURLToPath, not URL.pathname: pathname breaks on Windows
      // (leading slash before the drive letter, percent-encoded spaces).
      "openclaw/plugin-sdk/plugin-entry": fileURLToPath(
        new URL("./test-shims/plugin-entry.ts", import.meta.url),
      ),
      "openclaw/plugin-sdk": fileURLToPath(
        new URL("./test-shims/plugin-sdk.ts", import.meta.url),
      ),
    },
  },
});
