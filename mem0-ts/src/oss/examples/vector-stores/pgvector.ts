import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoPGVector() {
  console.log("\n=== Testing PGVector Store ===\n");

  const memory = new Memory({
    version: "v1.1",
    embedder: {
      // provider: "openai",
      // config: {
      //   apiKey: process.env.OPENAI_API_KEY || "",
      //   model: "text-embedding-3-small",
      // },
      provider: "ollama",
      config: {
        apiKey: "",
        model: "nomic-embed-text"
      }
    },
    vectorStore: {
      provider: "pgvector",
      config: {
        collectionName: "memories",
        dimension: 768,
        dbname: process.env.PGVECTOR_DB || "vectordb",
        user: process.env.PGVECTOR_USER || "postgres",
        password: process.env.PGVECTOR_PASSWORD || "postgres",
        host: process.env.PGVECTOR_HOST || "localhost",
        port: parseInt(process.env.PGVECTOR_PORT || "5432"),
        embeddingModelDims: 768,
        hnsw: true,
        // Connection pool configuration
        maxConnections: 20,
        connectionTimeoutMs: 30000,
        idleTimeoutMs: 10000,
        // Retry configuration
        maxRetries: 3,
        retryDelayMs: 1000,
        retryBackoffFactor: 2,
      },
    },
    llm: {
      provider: "ollama",
      config: {
        // apiKey: process.env.OPENAI_API_KEY || "",
        // model: "gpt-4-turbo-preview",
        apiKey: "",
        model: "gemma3:12b"
      },
    },
    historyDbPath: "memory.db",
  });

  await runTests(memory);
}

if (require.main === module) {
  if (!process.env.PGVECTOR_DB) {
    console.log("\nSkipping PGVector test - environment variables not set");
    process.exit(0);
  }
  demoPGVector();
}
