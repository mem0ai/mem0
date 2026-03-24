import { defineConfig } from "tsup";

const external = [
  "openai",
  "@anthropic-ai/sdk",
  "groq-sdk",
  "uuid",
  "pg",
  "zod",
  "better-sqlite3",
  "@qdrant/js-client-rest",
  "redis",
  "ollama",
  "@google/genai",
  "@mistralai/mistralai",
  "neo4j-driver",
  "@supabase/supabase-js",
  "@azure/search-documents",
  "@azure/identity",
  "cloudflare",
  "@cloudflare/workers-types",
  "@langchain/core",
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
