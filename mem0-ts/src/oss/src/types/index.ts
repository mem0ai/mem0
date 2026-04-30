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

/**
 * Normalizes snake_case config keys to camelCase for backward compatibility.
 * Some integrations (e.g. OpenClaw wizard) write snake_case keys, but mem0ai-ts
 * expects camelCase throughout. This helper transparently converts common aliases.
 */
export function normalizeMemoryConfig(config: any): any {
  if (!config || typeof config !== 'object') return config;

  const normalized = { ...config };

  // Normalize embedder config
  if (normalized.embedder?.config) {
    const ec = { ...normalized.embedder.config };
    if ('api_key' in ec && !('apiKey' in ec))          { ec.apiKey        = ec.api_key;        delete ec.api_key; }
    if ('embedding_dims' in ec && !('embeddingDims' in ec)) { ec.embeddingDims = ec.embedding_dims; delete ec.embedding_dims; }
    normalized.embedder = { ...normalized.embedder, config: ec };
  }

  // Normalize llm config
  if (normalized.llm?.config) {
    const lc = { ...normalized.llm.config };
    if ('api_key' in lc && !('apiKey' in lc)) { lc.apiKey = lc.api_key; delete lc.api_key; }
    normalized.llm = { ...normalized.llm, config: lc };
  }

  // Normalize vectorStore config
  if (normalized.vectorStore?.config) {
    const vc = { ...normalized.vectorStore.config };
    if ('api_key' in vc && !('apiKey' in vc))                       { vc.apiKey         = vc.api_key;              delete vc.api_key; }
    if ('collection_name' in vc && !('collectionName' in vc))       { vc.collectionName  = vc.collection_name;      delete vc.collection_name; }
    if ('embedding_model_dims' in vc && !('dimension' in vc))       { vc.dimension       = vc.embedding_model_dims; delete vc.embedding_model_dims; }
    // Force HTTP when host+port provided (avoids SSL errors on plain HTTP Qdrant)
    if ('host' in vc && !('url' in vc)) {
      vc.url = `http://${vc.host}:${vc.port || 6333}`;
      delete vc.host;
      delete vc.port;
    }
    normalized.vectorStore = { ...normalized.vectorStore, config: vc };
  }

  return normalized;
}
