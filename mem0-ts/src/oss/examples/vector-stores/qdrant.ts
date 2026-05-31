import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoQdrant() {
  console.log("\n=== Testing Qdrant Store ===\n");

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
      provider: "qdrant",
      config: {
        collectionName: "memories",
        embeddingModelDims: 1536,
        url: process.env.QDRANT_URL,
        apiKey: process.env.QDRANT_API_KEY,
        path: process.env.QDRANT_PATH,
        host: process.env.QDRANT_HOST,
        port: process.env.QDRANT_PORT
          ? parseInt(process.env.QDRANT_PORT)
          : undefined,
        onDisk: true,
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
  if (!process.env.QDRANT_URL && !process.env.QDRANT_HOST) {
    console.log("\nSkipping Qdrant test - environment variables not set");
    process.exit(0);
  }
  demoQdrant();
}
