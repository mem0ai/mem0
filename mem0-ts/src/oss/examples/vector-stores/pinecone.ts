import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoPinecone() {
  console.log("\n=== Testing Pinecone Store ===\n");

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
      provider: "pinecone",
      config: {
        apiKey: process.env.PINECONE_API_KEY,
        collectionName: "memories",
        embeddingModelDims: 1536,
        metric: "cosine",
        // Serverless configuration (recommended)
        serverlessConfig: {
          cloud: "aws",
          region: process.env.PINECONE_REGION || "us-east-1",
        },
        // Optional: Use namespace to isolate vectors
        namespace: process.env.PINECONE_NAMESPACE,
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
  if (!process.env.PINECONE_API_KEY) {
    console.log("\nSkipping Pinecone test - PINECONE_API_KEY not set");
    process.exit(0);
  }
  demoPinecone();
}
