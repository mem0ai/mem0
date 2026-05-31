import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoAzureAISearch() {
  console.log("\n=== Testing Azure AI Search Store ===\n");

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
      provider: "azure-ai-search",
      config: {
        collectionName: "memories",
        serviceName: process.env.AZURE_AI_SEARCH_SERVICE_NAME || "",
        apiKey: process.env.AZURE_AI_SEARCH_API_KEY,
        embeddingModelDims: 1536,
        compressionType: "none", // Options: "none", "scalar", "binary"
        useFloat16: false,
        hybridSearch: false,
        vectorFilterMode: "preFilter", // Options: "preFilter", "postFilter"
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
  if (!process.env.AZURE_AI_SEARCH_SERVICE_NAME) {
    console.log(
      "\nSkipping Azure AI Search test - AZURE_AI_SEARCH_SERVICE_NAME not set",
    );
    console.log("Set environment variables:");
    console.log("  - AZURE_AI_SEARCH_SERVICE_NAME (required)");
    console.log(
      "  - AZURE_AI_SEARCH_API_KEY (optional, uses DefaultAzureCredential if not set)",
    );
    console.log("  - OPENAI_API_KEY (required for embeddings and LLM)");
    process.exit(0);
  }
  demoAzureAISearch();
}
