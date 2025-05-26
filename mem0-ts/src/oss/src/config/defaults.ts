import { MemoryConfig } from "../types";

export const DEFAULT_MEMORY_CONFIG: MemoryConfig = {
  disableHistory: false,
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
      baseURL: "https://api.openai.com/v1",
      apiKey: process.env.OPENAI_API_KEY || "",
      model: "gpt-4-turbo-preview",
      modelProperties: undefined,
    },
  },
  enableGraph: false,
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
  historyStore: {
    provider: "sqlite",
    config: {
      historyDbPath: "memory.db",
    },
  },
};
