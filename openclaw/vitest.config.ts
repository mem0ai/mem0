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
      "openclaw/plugin-sdk/plugin-entry": new URL(
        "./test-shims/plugin-entry.ts",
        import.meta.url,
      ).pathname,
      "openclaw/plugin-sdk": new URL(
        "./test-shims/plugin-sdk.ts",
        import.meta.url,
      ).pathname,
    },
  },
});
