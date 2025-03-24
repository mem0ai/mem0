import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";
import dotenv from "dotenv";

// Load environment variables
dotenv.config();

export async function demoSupabase() {
  console.log("\n=== Testing Supabase Vector Store ===\n");

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
      provider: "supabase",
      config: {
        collectionName: "memories",
        embeddingModelDims: 1536,
        supabaseUrl: process.env.SUPABASE_URL || "",
        supabaseKey: process.env.SUPABASE_KEY || "",
        tableName: "memories",
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
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_KEY) {
    console.log("\nSkipping Supabase test - environment variables not set");
    process.exit(0);
  }
  demoSupabase();
}
