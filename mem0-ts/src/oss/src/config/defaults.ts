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
  enableGraph: true,
  graphStore: {
    provider: "apache_age",
    config: {
      host: process.env.AGE_HOST || process.env.DATABASE_HOST || "localhost",
      port: parseInt(process.env.AGE_PORT || process.env.DATABASE_PORT || "5432"),
      database: process.env.AGE_DATABASE || process.env.DATABASE_NAME || "whatsapp_assistant",
      username: process.env.AGE_USERNAME || process.env.DATABASE_USER || "postgres",
      password: process.env.AGE_PASSWORD || process.env.DATABASE_PASSWORD || "password",
      graphName: process.env.AGE_GRAPH_NAME || "memory_graph",
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
