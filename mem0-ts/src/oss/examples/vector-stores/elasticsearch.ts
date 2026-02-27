import { Memory } from "../../src";
import { runTests } from "../utils/test-utils";

export async function demoElasticsearch() {
  console.log("\n=== Testing Elasticsearch Store ===\n");

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
      provider: "elasticsearch",
      config: {
        collectionName: "memories",
        embeddingModelDims: 1536,
        // For Elastic Cloud:
        // cloudId: process.env.ELASTICSEARCH_CLOUD_ID,
        // apiKey: process.env.ELASTICSEARCH_API_KEY,
        // For self-hosted:
        host: process.env.ELASTICSEARCH_HOST || "http://localhost",
        port: process.env.ELASTICSEARCH_PORT
          ? parseInt(process.env.ELASTICSEARCH_PORT)
          : 9200,
        user: process.env.ELASTICSEARCH_USER || "elastic",
        password: process.env.ELASTICSEARCH_PASSWORD || "password",
        verifyCerts: process.env.ELASTICSEARCH_VERIFY_CERTS !== "false",
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
  const hasElasticCloud = process.env.ELASTICSEARCH_CLOUD_ID;
  const hasElasticHost = process.env.ELASTICSEARCH_HOST;
  const hasAuth =
    process.env.ELASTICSEARCH_API_KEY ||
    (process.env.ELASTICSEARCH_USER && process.env.ELASTICSEARCH_PASSWORD);

  if (!hasElasticCloud && !hasElasticHost && !hasAuth) {
    console.log(
      "\nSkipping Elasticsearch test - environment variables not set",
    );
    console.log("Set one of the following configurations:");
    console.log(
      "  - ELASTICSEARCH_CLOUD_ID + ELASTICSEARCH_API_KEY (for Elastic Cloud)",
    );
    console.log(
      "  - ELASTICSEARCH_HOST + ELASTICSEARCH_USER + ELASTICSEARCH_PASSWORD (for self-hosted)",
    );
    process.exit(0);
  }
  demoElasticsearch();
}
