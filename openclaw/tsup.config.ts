import { defineConfig } from "tsup";
import pkg from "./package.json";

export default defineConfig({
  entry: ["index.ts", "fs-safe.ts"],
  format: ["esm"],
  splitting: true,
  dts: true,
  sourcemap: true,
  clean: true,
  external: [/^node:/, /^openclaw\//, "fs", "os", "path", "url", "readline", "module",
             "mem0ai", /^mem0ai\//, "better-sqlite3", "@sinclair/typebox"],
  define: {
    __OPENCLAW_PLUGIN_VERSION__: JSON.stringify(pkg.version),
  },
});
