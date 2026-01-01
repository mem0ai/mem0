import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoS3Vectors() {
  console.log("\n=== Testing S3 Vectors Store ===\n");

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
      provider: "s3_vectors",
      config: {
        vectorBucketName: process.env.S3_VECTORS_BUCKET_NAME || "mem0-vectors",
        collectionName: "memories",
        embeddingModelDims: 1536,
        distanceMetric: "cosine",
        region: process.env.AWS_REGION || "us-east-1",
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
  if (!process.env.S3_VECTORS_BUCKET_NAME) {
    console.log("\nSkipping S3 Vectors test - S3_VECTORS_BUCKET_NAME not set");
    console.log(
      "Set AWS credentials and S3_VECTORS_BUCKET_NAME to run this example",
    );
    process.exit(0);
  }
  demoS3Vectors();
}
