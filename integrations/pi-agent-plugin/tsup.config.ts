import { defineConfig } from "tsup";
import { packageHandoff } from "../agent-plugin-core/build/package_handoff.mjs";

export default defineConfig({
  entry: ["src/index.ts", "src/entry.ts"],
  format: ["esm"],
  splitting: true,
  dts: true,
  sourcemap: true,
  clean: true,
  onSuccess: () => packageHandoff(),
  external: [
    /^node:/,
    /^@earendil-works\//,
    "typebox",
    "mem0ai",
    /^mem0ai\//,
  ],
});
