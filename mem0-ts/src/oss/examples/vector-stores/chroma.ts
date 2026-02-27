import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoChroma() {
  console.log("\n=== Testing Chroma Store ===\n");

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
      provider: "chroma",
      config: {
        collectionName: "memories",
        // Local storage (default)
        path: process.env.CHROMA_PATH || "./chroma-data",
        // Or use server connection:
        // host: process.env.CHROMA_HOST,
        // port: process.env.CHROMA_PORT ? parseInt(process.env.CHROMA_PORT) : undefined,
        // Or use ChromaDB Cloud:
        // apiKey: process.env.CHROMA_API_KEY,
        // tenant: process.env.CHROMA_TENANT,
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

export async function demoChromaServer() {
  console.log("\n=== Testing Chroma Server Store ===\n");

  if (!process.env.CHROMA_HOST) {
    console.log("Skipping Chroma server test - CHROMA_HOST not set");
    return;
  }

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
      provider: "chroma",
      config: {
        collectionName: "memories",
        host: process.env.CHROMA_HOST,
        port: process.env.CHROMA_PORT
          ? parseInt(process.env.CHROMA_PORT)
          : 8000,
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

export async function demoChromaCloud() {
  console.log("\n=== Testing Chroma Cloud Store ===\n");

  if (!process.env.CHROMA_API_KEY || !process.env.CHROMA_TENANT) {
    console.log(
      "Skipping Chroma Cloud test - CHROMA_API_KEY or CHROMA_TENANT not set",
    );
    return;
  }

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
      provider: "chroma",
      config: {
        collectionName: "memories",
        apiKey: process.env.CHROMA_API_KEY,
        tenant: process.env.CHROMA_TENANT,
        database: process.env.CHROMA_DATABASE || "mem0",
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
  // Run local demo by default
  demoChroma().catch(console.error);
}
