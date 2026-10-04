import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  dts: true,
  sourcemap: true,
  clean: true,
  // The harness runtime and the Mem0 SDK are provided by the host / installed
  // separately; keep them out of the bundle.
  external: [/^node:/, /^@deepseek-ai\//, "mem0ai", /^mem0ai\//],
});
