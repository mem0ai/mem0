import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoRedis() {
  console.log("\n=== Testing Redis Store ===\n");

  const memory = new Memory({
    version: "v1.1",
    embedder: {
      provider: "openai",
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "text-embedding-3-small",
      },
    },
    vectorStore: {
      provider: "redis",
      config: {
        collectionName: "memories",
        embeddingModelDims: 1536,
        redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
        username: process.env.REDIS_USERNAME,
        password: process.env.REDIS_PASSWORD,
      },
    },
    llm: {
      provider: "openai",
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "gpt-4-turbo-preview",
      },
    },
    historyDbPath: "memory.db",
  });

  await runTests(memory);
}

if (require.main === module) {
  if (!process.env.REDIS_URL) {
    console.log("\nSkipping Redis test - environment variables not set");
    process.exit(0);
  }
  demoRedis();
}
