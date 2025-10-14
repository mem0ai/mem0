import { Memory } from "../../src";
import dotenv from "dotenv";

dotenv.config();

async function togetherEmbeddingExample() {
  console.log("🚀 Together AI Embedding Example");

  // Initialize Memory with Together AI embedder
  const memory = new Memory({
    version: "v1.1",
    embedder: {
      provider: "together",
      config: {
        apiKey: process.env.TOGETHER_API_KEY || "",
        model: "togethercomputer/m2-bert-80M-8k-retrieval", // Default model
      },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: "together-memories",
        dimension: 768, // M2-BERT-80M has 768 dimensions
      },
    },
    llm: {
      provider: "openai", // You can use any LLM provider
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "gpt-4-turbo-preview",
      },
    },
  });

  const userId = "user-123";

  try {
    // Add some memories
    console.log("📝 Adding memories...");
    await memory.add("I love programming in TypeScript", { userId });
    await memory.add("My favorite AI model is Llama 3.3", { userId });
    await memory.add("I enjoy building applications with Together AI", { userId });

    // Search for memories
    console.log("🔍 Searching memories...");
    const searchResults = await memory.search(
      "What programming languages do I like?",
      { userId },
    );

    console.log("Search Results:", searchResults);

    // Get all memories
    console.log("📚 Getting all memories...");
    const allMemories = await memory.getAll({ userId });
    console.log("All Memories:", allMemories);

  } catch (error) {
    console.error("❌ Error:", error);
  }
}

// Example with different Together AI embedding models
async function differentModelsExample() {
  console.log("🔄 Different Together AI Models Example");

  // Using M2-BERT-80M-32K-Retrieval for longer context
  const memoryLongContext = new Memory({
    version: "v1.1",
    embedder: {
      provider: "together",
      config: {
        apiKey: process.env.TOGETHER_API_KEY || "",
        model: "togethercomputer/m2-bert-80M-32k-retrieval", // 32K context window
      },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: "long-context-memories",
        dimension: 768,
      },
    },
    llm: {
      provider: "openai",
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "gpt-4-turbo-preview",
      },
    },
  });

  // Using BGE-Large-EN-v1.5 for better performance
  const memoryBGE = new Memory({
    version: "v1.1",
    embedder: {
      provider: "together",
      config: {
        apiKey: process.env.TOGETHER_API_KEY || "",
        model: "BAAI/bge-large-en-v1.5", // Better performance model
      },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: "bge-memories",
        dimension: 1024, // BGE-Large has 1024 dimensions
      },
    },
    llm: {
      provider: "openai",
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "gpt-4-turbo-preview",
      },
    },
  });

  console.log("✅ Different models configured successfully!");
}

// Export functions for use in other modules
export { togetherEmbeddingExample, differentModelsExample };

// Run examples if this file is executed directly
if (typeof require !== 'undefined' && require.main === module) {
  togetherEmbeddingExample()
    .then(() => differentModelsExample())
    .then(() => console.log("🎉 Examples completed!"))
    .catch(console.error);
} 