import { Memory } from "../../src/memory";
import { MemoryConfig } from "../../src/types";

async function main() {
  // LMStudio configuration
  const config: MemoryConfig = {
    llm: {
      provider: "lmstudio",
      config: {
        model: "llama-3.2-1b-instruct", // or any model you have loaded in LMStudio
        baseUrl: "http://localhost:1234/v1", // default LMStudio server URL
      },
    },
    embedder: {
      provider: "openai", // You can use OpenAI embeddings or any other supported embedder
      config: {
        apiKey: process.env.OPENAI_API_KEY,
        model: "text-embedding-3-small",
      },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: "lmstudio-memories",
      },
    },
  };

  // Initialize Memory with LMStudio
  const memory = new Memory(config);

  const userId = "user-123";

  try {
    // Add some memories
    console.log("Adding memories...");
    await memory.add("I love playing guitar and listening to jazz music.", {
      userId,
    });
    await memory.add("I work as a software engineer at a tech startup.", {
      userId,
    });
    await memory.add("My favorite programming language is TypeScript.", {
      userId,
    });

    // Search for memories
    console.log("\nSearching for music-related memories:");
    const musicMemories = await memory.search("music", { userId });
    console.log(musicMemories);

    console.log("\nSearching for work-related memories:");
    const workMemories = await memory.search("work programming", { userId });
    console.log(workMemories);

    // Get all memories
    console.log("\nAll memories:");
    const allMemories = await memory.getAll({ userId });
    console.log(allMemories);

    // Update a memory
    console.log("\nUpdating memory...");
    await memory.add(
      "I recently started learning to play piano alongside guitar.",
      { userId },
    );

    // Search again to see updated results
    console.log("\nSearching for music after update:");
    const updatedMusicMemories = await memory.search("music instruments", {
      userId,
    });
    console.log(updatedMusicMemories);
  } catch (error) {
    console.error("Error:", error);
  }
}

// Run the example
main().catch(console.error);
