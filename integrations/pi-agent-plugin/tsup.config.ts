import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts", "src/entry.ts"],
  format: ["esm"],
  splitting: true,
  dts: true,
  sourcemap: true,
  clean: true,
  external: [
    /^node:/,
    /^@earendil-works\//,
    "typebox",
    "mem0ai",
    /^mem0ai\//,
  ],
});
