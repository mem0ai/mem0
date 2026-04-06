import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["index.ts", "fs-safe.ts"],
  format: ["esm"],
  splitting: true,
  dts: true,
  sourcemap: true,
  clean: true,
  external: [/^node:/, /^openclaw\//, "fs", "os", "path", "url", "readline", "module"],
});
