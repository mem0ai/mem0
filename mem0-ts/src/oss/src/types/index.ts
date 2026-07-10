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
  // HuggingFace TEI / OpenAI-compatible inference endpoint base URL.
  huggingfaceBaseUrl?: string;
}

export interface VertexAIConfig extends EmbeddingConfig {
  vertexCredentialsJson?: string;
  googleServiceAccountJson?: string | Record<string, any>;
  googleProjectId?: string;
  location?: string;
  memoryAddEmbeddingType?: string;
  memoryUpdateEmbeddingType?: string;
  memorySearchEmbeddingType?: string;
}
export type { ValkeyConfig } from "./valkey";

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
  vllmBaseURL?: string;
  vllm_base_url?: string;
  url?: string;
  config?: Record<string, any>;
  apiKey?: string;
  model?: string | any;
  modelProperties?: Record<string, any>;
  timeout?: number;
  temperature?: number;
  topP?: number;
  maxTokens?: number;
  // AWS Bedrock provider config (used when provider === "aws_bedrock").
  // Credentials otherwise resolve via the standard AWS credential chain.
  awsRegion?: string;
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  awsSessionToken?: string;
  // Optional pre-constructed client (e.g. BedrockRuntimeClient) for DI/testing.
  client?: any;
}

export interface RerankerConfig {
  apiKey?: string;
  /** The reranker model to use. Default varies by provider. */
  model?: string;
  /** Maximum number of documents to return after reranking. Default: unset (return all). */
  topK?: number;
  /** `cohere` only. Return document texts in the response. Default: `false`. */
  returnDocuments?: boolean;
  /** `cohere` only. Maximum number of chunks per document. Default: unset. */
  maxChunksPerDoc?: number;
  /**
   * `sentence_transformer` / `huggingface` only. Transformers.js device, e.g.
   * `"cpu"`, `"wasm"`, `"webgpu"`. Default: unset (auto-detect).
   */
  device?: string;
  /** `huggingface` only. Max token length per query-document pair. Default: `512`. */
  maxLength?: number;
  /**
   * `sentence_transformer` / `huggingface` only. Sigmoid-normalize raw logits
   * to `[0, 1]`. Default: `true`; set `false` to surface raw logits.
   */
  normalize?: boolean;
  /** No-op: a search reranks a small candidate set in one forward pass. */
  batchSize?: number;
  /** No-op in this runtime. */
  showProgressBar?: boolean;
  /**
   * `llm_reranker` only. LLM provider used to build the scoring LLM when
   * `llm` is not set. Default: `"openai"`.
   */
  provider?: string;
  /** `llm_reranker` only. Temperature for LLM generation. Default: `0.0`. */
  temperature?: number;
  /** `llm_reranker` only. Maximum tokens for the LLM response. Default: `100`. */
  maxTokens?: number;
  /**
   * `llm_reranker` only. Nested LLM configuration. When set, it overrides the
   * top-level `provider`/`model`/`temperature`/`maxTokens`/`apiKey`, which
   * then only act as defaults for fields missing from `llm.config`.
   */
  llm?: {
    provider: string;
    config: LLMConfig;
  };
  [key: string]: any;
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
  reranker?: {
    provider: string;
    config: RerankerConfig;
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
  /** Relevance score added by the reranker, alongside (not replacing) `score`. */
  rerankScore?: number;
  metadata?: Record<string, any>;
  attributedTo?: string;
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
      vertexCredentialsJson: z.string().optional(),
      googleServiceAccountJson: z
        .union([z.string(), z.record(z.string(), z.any())])
        .optional(),
      googleProjectId: z.string().optional(),
      location: z.string().optional(),
      memoryAddEmbeddingType: z.string().optional(),
      memoryUpdateEmbeddingType: z.string().optional(),
      memorySearchEmbeddingType: z.string().optional(),
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
    config: z
      .object({
        apiKey: z.string().optional(),
        model: z.union([z.string(), z.any()]).optional(),
        modelProperties: z.record(z.string(), z.any()).optional(),
        baseURL: z.string().optional(),
        vllmBaseURL: z.string().optional(),
        vllm_base_url: z.string().optional(),
        url: z.string().optional(),
        timeout: z.number().optional(),
        temperature: z.number().optional(),
        topP: z.number().optional(),
        maxTokens: z.number().optional(),
        awsRegion: z.string().optional(),
        awsAccessKeyId: z.string().optional(),
        awsSecretAccessKey: z.string().optional(),
        awsSessionToken: z.string().optional(),
        client: z.any().optional(),
      })
      .passthrough(),
  }),
  historyDbPath: z.string().optional(),
  customInstructions: z.string().optional(),
  historyStore: z
    .object({
      provider: z.string(),
      config: z.record(z.string(), z.any()),
    })
    .optional(),
  reranker: z
    .object({
      provider: z.string(),
      config: z.record(z.string(), z.any()),
    })
    .optional(),
  disableHistory: z.boolean().optional(),
});
