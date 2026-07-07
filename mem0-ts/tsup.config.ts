import { defineConfig } from "tsup";
import pkg from "./package.json";

const external = [
  "openai",
  "@anthropic-ai/sdk",
  "@aws-sdk/client-s3vectors",
  "groq-sdk",
  "uuid",
  "pg",
  "zod",
  "better-sqlite3",
  "cassandra-driver",
  "@pinecone-database/pinecone",
  "@qdrant/js-client-rest",
  "redis",
  "iovalkey",
  "ollama",
  "@google/genai",
  "@google-cloud/aiplatform",
  "@mistralai/mistralai",
  "@supabase/supabase-js",
  "@upstash/vector",
  "@azure/search-documents",
  "@azure/identity",
  "cloudflare",
  "@cloudflare/workers-types",
  "@langchain/core",
  "fastembed",
  "compromise",
  "natural",
  "mysql2",
  "@turbopuffer/turbopuffer",
  "@opensearch-project/opensearch",
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
