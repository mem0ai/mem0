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
      model: "gpt-5-mini",
      modelProperties: undefined,
    },
  },
  historyStore: {
    provider: "sqlite",
    config: {
      historyDbPath: "memory.db",
    },
  },
};
