import dotenv from "dotenv";
import { MistralEmbedder } from "../../src/embeddings/mistral";

// Load environment variables
dotenv.config();

async function testMistralEmbedder() {
  // Check for API key
  if (!process.env.MISTRAL_API_KEY) {
    console.error("MISTRAL_API_KEY environment variable is required");
    process.exit(1);
  }

  console.log("Testing Mistral Embedder implementation...");

  // Initialize MistralEmbedder
  const mistralEmbedder = new MistralEmbedder({
    apiKey: process.env.MISTRAL_API_KEY,
    model: "mistral-embed",
  });

  try {
    // Test single embedding
    console.log("Testing single text embedding:");
    const singleText = "The Eiffel Tower is in Paris.";
    const singleEmbedding = await mistralEmbedder.embed(singleText);

    console.log(`Input: "${singleText}"`);
    console.log(`Embedding length: ${singleEmbedding.length}`);
    console.log(`First 5 values: ${singleEmbedding.slice(0, 5).join(", ")}\n`);

    // Test batch embedding
    console.log("Testing batch text embedding:");
    const batchTexts = [
      "The Eiffel Tower is in Paris.",
      "The Colosseum is in Rome.",
      "The Great Wall is in China.",
    ];
    const batchEmbeddings = await mistralEmbedder.embedBatch(batchTexts);

    batchTexts.forEach((text, index) => {
      console.log(`Input: "${text}"`);
      console.log(`Embedding length: ${batchEmbeddings[index].length}`);
      console.log(
        `First 5 values: ${batchEmbeddings[index].slice(0, 5).join(", ")}\n`
      );
    });

    console.log("✅ All embedder tests completed successfully");
  } catch (error) {
    console.error("❌ Error testing Mistral Embedder:", error);
  }
}

testMistralEmbedder().catch(console.error);
