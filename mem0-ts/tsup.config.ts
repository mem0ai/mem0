import { defineConfig } from "tsup";
import pkg from "./package.json";

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
  "@supabase/supabase-js",
  "@azure/search-documents",
  "@azure/identity",
  "cloudflare",
  "@cloudflare/workers-types",
  "@langchain/core",
  "compromise",
  "natural",
];

const define = {
  __MEM0_SDK_VERSION__: JSON.stringify(pkg.version),
};

export default defineConfig([
  {
    entry: ["src/client/index.ts"],
    format: ["cjs", "esm"],
    dts: true,
    sourcemap: true,
    external,
    define,
  },
  {
    entry: ["src/oss/src/index.ts"],
    outDir: "dist/oss",
    format: ["cjs", "esm"],
    dts: true,
    sourcemap: true,
    external,
    define,
  },
]);
