import { defineConfig } from "tsup";

const external = [
  "openai",
  "@anthropic-ai/sdk",
  "groq-sdk",
  "uuid",
  "pg",
  "zod",
  "sqlite3",
  "@qdrant/js-client-rest",
  "redis",
];

export default defineConfig([
  {
    entry: ["src/client/index.ts"],
    format: ["cjs", "esm"],
    dts: true,
    sourcemap: true,
    external,
  },
  {
    entry: ["src/oss/src/index.ts"],
    outDir: "dist/oss",
    format: ["cjs", "esm"],
    dts: true,
    sourcemap: true,
    external,
  },
]);
