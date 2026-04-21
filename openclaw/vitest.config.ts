import { defineConfig } from "vitest/config";

export default defineConfig({
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
