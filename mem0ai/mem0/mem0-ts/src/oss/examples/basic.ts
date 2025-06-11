import { Memory } from "../src";
import dotenv from "dotenv";

// Load environment variables
dotenv.config();

async function demoDefaultConfig() {
  console.log("\n=== Testing Default Config ===\n");

  const memory = new Memory();
  await runTests(memory);
}

async function run_examples() {
  // Test default config
  await demoDefaultConfig();
}

run_examples();

async function runTests(memory: Memory) {
  try {
    // Reset all memories
    console.log("\nResetting all memories...");
    await memory.reset();
    console.log("All memories reset");

    // Add a single memory
    console.log("\nAdding a single memory...");
    const result1 = await memory.add(
      "Hi, my name is John and I am a software engineer.",
      {
        userId: "john",
      },
    );
    console.log("Added memory:", result1);

    // Add multiple messages
    console.log("\nAdding multiple messages...");
    const result2 = await memory.add(
      [
        { role: "user", content: "What is your favorite city?" },
        { role: "assistant", content: "I love Paris, it is my favorite city." },
      ],
      {
        userId: "john",
      },
    );
    console.log("Added messages:", result2);

    // Trying to update the memory
    const result3 = await memory.add(
      [
        { role: "user", content: "What is your favorite city?" },
        {
          role: "assistant",
          content: "I love New York, it is my favorite city.",
        },
      ],
      {
        userId: "john",
      },
    );
    console.log("Updated messages:", result3);

    // Get a single memory
    console.log("\nGetting a single memory...");
    if (result1.results && result1.results.length > 0) {
      const singleMemory = await memory.get(result1.results[0].id);
      console.log("Single memory:", singleMemory);
    } else {
      console.log("No memory was added in the first step");
    }

    // Updating this memory
    const result4 = await memory.update(
      result1.results[0].id,
      "I love India, it is my favorite country.",
    );
    console.log("Updated memory:", result4);

    // Get all memories
    console.log("\nGetting all memories...");
    const allMemories = await memory.getAll({
      userId: "john",
    });
    console.log("All memories:", allMemories);

    // Search for memories
    console.log("\nSearching memories...");
    const searchResult = await memory.search("What do you know about Paris?", {
      userId: "john",
    });
    console.log("Search results:", searchResult);

    // Get memory history
    if (result1.results && result1.results.length > 0) {
      console.log("\nGetting memory history...");
      const history = await memory.history(result1.results[0].id);
      console.log("Memory history:", history);
    }

    // Delete a memory
    if (result1.results && result1.results.length > 0) {
      console.log("\nDeleting a memory...");
      await memory.delete(result1.results[0].id);
      console.log("Memory deleted successfully");
    }

    // Reset all memories
    console.log("\nResetting all memories...");
    await memory.reset();
    console.log("All memories reset");
  } catch (error) {
    console.error("Error:", error);
  }
}

async function demoLocalMemory() {
  console.log("\n=== Testing In-Memory Vector Store with Ollama===\n");

  const memory = new Memory({
    version: "v1.1",
    embedder: {
      provider: "ollama",
      config: {
        model: "nomic-embed-text:latest",
      },
    },
    vectorStore: {
      provider: "memory",
      config: {
        collectionName: "memories",
        dimension: 768, // 768 is the dimension of the nomic-embed-text model
      },
    },
    llm: {
      provider: "ollama",
      config: {
        model: "llama3.1:8b",
      },
    },
    // historyDbPath: "memory.db",
  });

  await runTests(memory);
}

async function demoMemoryStore() {
  console.log("\n=== Testing In-Memory Vector Store ===\n");

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
      provider: "memory",
      config: {
        collectionName: "memories",
        dimension: 1536,
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

async function demoPGVector() {
  console.log("\n=== Testing PGVector Store ===\n");

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
      provider: "pgvector",
      config: {
        collectionName: "memories",
        dimension: 1536,
        dbname: process.env.PGVECTOR_DB || "vectordb",
        user: process.env.PGVECTOR_USER || "postgres",
        password: process.env.PGVECTOR_PASSWORD || "postgres",
        host: process.env.PGVECTOR_HOST || "localhost",
        port: parseInt(process.env.PGVECTOR_PORT || "5432"),
        embeddingModelDims: 1536,
        hnsw: true,
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

async function demoQdrant() {
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

async function demoRedis() {
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

async function demoGraphMemory() {
  console.log("\n=== Testing Graph Memory Store ===\n");

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
      provider: "memory",
      config: {
        collectionName: "memories",
        dimension: 1536,
      },
    },
    llm: {
      provider: "openai",
      config: {
        apiKey: process.env.OPENAI_API_KEY || "",
        model: "gpt-4-turbo-preview",
      },
    },
    graphStore: {
      provider: "neo4j",
      config: {
        url: process.env.NEO4J_URL || "neo4j://localhost:7687",
        username: process.env.NEO4J_USERNAME || "neo4j",
        password: process.env.NEO4J_PASSWORD || "password",
      },
      llm: {
        provider: "openai",
        config: {
          model: "gpt-4-turbo-preview",
        },
      },
    },
    historyDbPath: "memory.db",
  });

  try {
    // Reset all memories
    await memory.reset();

    // Add memories with relationships
    const result = await memory.add(
      [
        {
          role: "user",
          content: "Alice is Bob's sister and works as a doctor.",
        },
        {
          role: "assistant",
          content:
            "I understand that Alice and Bob are siblings and Alice is a medical professional.",
        },
        { role: "user", content: "Bob is married to Carol who is a teacher." },
      ],
      {
        userId: "john",
      },
    );
    console.log("Added memories with relationships:", result);

    // Search for connected information
    const searchResult = await memory.search(
      "Tell me about Bob's family connections",
      {
        userId: "john",
      },
    );
    console.log("Search results with graph relationships:", searchResult);
  } catch (error) {
    console.error("Error in graph memory demo:", error);
  }
}

async function main() {
  // Test in-memory store
  await demoMemoryStore();

  // Test in-memory store with Ollama
  await demoLocalMemory();

  // Test graph memory if Neo4j environment variables are set
  if (
    process.env.NEO4J_URL &&
    process.env.NEO4J_USERNAME &&
    process.env.NEO4J_PASSWORD
  ) {
    await demoGraphMemory();
  } else {
    console.log(
      "\nSkipping Graph Memory test - Neo4j environment variables not set",
    );
  }

  // Test PGVector store if environment variables are set
  if (process.env.PGVECTOR_DB) {
    await demoPGVector();
  } else {
    console.log("\nSkipping PGVector test - environment variables not set");
  }

  // Test Qdrant store if environment variables are set
  if (
    process.env.QDRANT_URL ||
    (process.env.QDRANT_HOST && process.env.QDRANT_PORT)
  ) {
    await demoQdrant();
  } else {
    console.log("\nSkipping Qdrant test - environment variables not set");
  }

  // Test Redis store if environment variables are set
  if (process.env.REDIS_URL) {
    await demoRedis();
  } else {
    console.log("\nSkipping Redis test - environment variables not set");
  }
}

main();
