import { z } from "zod";

export interface Message {
  role: string;
  content: string;
}

export interface EmbeddingConfig {
  apiKey: string;
  model?: string;
}

export interface VectorStoreConfig {
  collectionName: string;
  dimension?: number;
  [key: string]: any;
}

export interface LLMConfig {
  apiKey: string;
  model?: string;
}

export interface GraphStoreConfig {
  config?: any;
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
  historyDbPath?: string;
  customPrompt?: string;
  graphStore?: GraphStoreConfig;
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
  userId?: string;
  agentId?: string;
  runId?: string;
  [key: string]: any;
}

export interface SearchResult {
  results: MemoryItem[];
  relations?: any[];
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
      apiKey: z.string(),
      model: z.string().optional(),
    }),
  }),
  vectorStore: z.object({
    provider: z.string(),
    config: z
      .object({
        collectionName: z.string(),
        dimension: z.number().optional(),
      })
      .passthrough(),
  }),
  llm: z.object({
    provider: z.string(),
    config: z.object({
      apiKey: z.string(),
      model: z.string().optional(),
    }),
  }),
  historyDbPath: z.string().optional(),
  customPrompt: z.string().optional(),
  graphStore: z
    .object({
      config: z.any().optional(),
    })
    .optional(),
});
