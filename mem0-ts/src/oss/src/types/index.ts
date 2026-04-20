import { z } from "zod";

export interface MultiModalMessages {
  type: "image_url";
  image_url: {
    url: string;
  };
}

export interface Message {
  role: string;
  content: string | MultiModalMessages;
}

export interface EmbeddingConfig {
  apiKey?: string;
  model?: string | any;
  baseURL?: string;
  url?: string;
  embeddingDims?: number;
  modelProperties?: Record<string, any>;
}

export interface VectorStoreConfig {
  collectionName?: string;
  dimension?: number;
  dbPath?: string;
  client?: any;
  instance?: any;
  [key: string]: any;
}

export interface HistoryStoreConfig {
  provider: string;
  config: {
    historyDbPath?: string;
    supabaseUrl?: string;
    supabaseKey?: string;
    tableName?: string;
  };
}

export interface LLMConfig {
  provider?: string;
  baseURL?: string;
  url?: string;
  config?: Record<string, any>;
  apiKey?: string;
  model?: string | any;
  modelProperties?: Record<string, any>;
  timeout?: number;
}

export interface MemoryConfig {
  version?: string;
  embedder: {
    provider: string;
    config: EmbeddingConfig;
  };
  vectorStore: {
    provider: string;
    config: VectorStoreConfig;
  };
  llm: {
    provider: string;
    config: LLMConfig;
  };
  historyStore?: HistoryStoreConfig;
  disableHistory?: boolean;
  historyDbPath?: string;
  customInstructions?: string;
}

export interface MemoryItem {
  id: string;
  memory: string;
  hash?: string;
  createdAt?: string;
  updatedAt?: string;
  score?: number;
  metadata?: Record<string, any>;
}

export interface SearchFilters {
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  [key: string]: any;
}

export interface SearchResult {
  results: MemoryItem[];
}

export interface VectorStoreResult {
  id: string;
  payload: Record<string, any>;
  score?: number;
}

export const MemoryConfigSchema = z.object({
  version: z.string().optional(),
  embedder: z.object({
    provider: z.string(),
    config: z.object({
      modelProperties: z.record(z.string(), z.any()).optional(),
      apiKey: z.string().optional(),
      model: z.union([z.string(), z.any()]).optional(),
      baseURL: z.string().optional(),
      embeddingDims: z.number().optional(),
      url: z.string().optional(),
    }),
  }),
  vectorStore: z.object({
    provider: z.string(),
    config: z
      .object({
        collectionName: z.string().optional(),
        dimension: z.number().optional(),
        dbPath: z.string().optional(),
        client: z.any().optional(),
      })
      .passthrough(),
  }),
  llm: z.object({
    provider: z.string(),
    config: z.object({
      apiKey: z.string().optional(),
      model: z.union([z.string(), z.any()]).optional(),
      modelProperties: z.record(z.string(), z.any()).optional(),
      baseURL: z.string().optional(),
      url: z.string().optional(),
      timeout: z.number().optional(),
    }),
  }),
  historyDbPath: z.string().optional(),
  customInstructions: z.string().optional(),
  historyStore: z
    .object({
      provider: z.string(),
      config: z.record(z.string(), z.any()),
    })
    .optional(),
  disableHistory: z.boolean().optional(),
});
