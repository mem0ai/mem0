import dotenv from "dotenv";
import { demoMemoryStore } from "./memory";
import { demoSupabase } from "./supabase";
// import { demoQdrant } from "./qdrant";
// import { demoRedis } from "./redis";
// import { demoPGVector } from "./pgvector";

// Load environment variables
dotenv.config();

async function main() {
  const args = process.argv.slice(2);
  const selectedStore = args[0]?.toLowerCase();

  const stores: Record<string, () => Promise<void>> = {
    // memory: demoMemoryStore,
    supabase: demoSupabase,
    // Uncomment these as they are implemented
    // qdrant: demoQdrant,
    // redis: demoRedis,
    // pgvector: demoPGVector,
  };

  if (selectedStore) {
    const demo = stores[selectedStore];
    if (demo) {
      try {
        await demo();
      } catch (error) {
        console.error(`\nError running ${selectedStore} demo:`, error);
        if (selectedStore !== "memory") {
          console.log("\nFalling back to memory store...");
          await stores.memory();
        }
      }
    } else {
      console.log(`\nUnknown vector store: ${selectedStore}`);
      console.log("Available stores:", Object.keys(stores).join(", "));
    }
    return;
  }

  // If no store specified, run all available demos
  for (const [name, demo] of Object.entries(stores)) {
    try {
      await demo();
    } catch (error) {
      console.error(`\nError running ${name} demo:`, error);
    }
  }
}

main().catch(console.error);
