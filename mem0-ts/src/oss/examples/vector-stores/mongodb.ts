import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoMongoDB() {
  console.log("\n=== Testing MongoDB Atlas Vector Store ===\n");

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
      provider: "mongodb",
      config: {
        mongoUri: process.env.MONGODB_URI || "",
        dbName: process.env.MONGODB_DB_NAME || "mem0",
        collectionName: "memories",
        embeddingModelDims: 1536,
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
  if (!process.env.MONGODB_URI) {
    console.log("\nSkipping MongoDB test - MONGODB_URI not set");
    console.log(
      "Set MONGODB_URI and optionally MONGODB_DB_NAME to run this example",
    );
    process.exit(0);
  }
  demoMongoDB();
}
