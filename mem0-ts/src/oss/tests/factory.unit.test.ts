/**
 * Factory unit tests — EmbedderFactory, LLMFactory, VectorStoreFactory, HistoryManagerFactory.
 * Mocks all provider modules to avoid external dependency crashes.
 */
/// <reference types="jest" />

// Mock all provider modules before importing factory
jest.mock("../src/embeddings/openai", () => ({
  OpenAIEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "openai-embedder", config })),
}));
jest.mock("../src/embeddings/ollama", () => ({
  OllamaEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "ollama-embedder", config })),
}));
jest.mock("../src/embeddings/google", () => ({
  GoogleEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "google-embedder", config })),
}));
jest.mock("../src/embeddings/fastembed", () => ({
  FastEmbedEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "fastembed-embedder", config })),
}));
jest.mock("../src/embeddings/azure", () => ({
  AzureOpenAIEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "azure-embedder", config })),
}));
jest.mock("../src/embeddings/langchain", () => ({
  LangchainEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "langchain-embedder", config })),
}));
jest.mock("../src/embeddings/lmstudio", () => ({
  LMStudioEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "lmstudio-embedder", config })),
}));
jest.mock("../src/embeddings/vertexai", () => ({
  VertexAIEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "vertexai-embedder", config })),
}));
jest.mock("../src/embeddings/together", () => ({
  TogetherEmbedder: jest
    .fn()
    .mockImplementation((config) => ({ type: "together-embedder", config })),
}));

jest.mock("../src/llms/openai", () => ({
  OpenAILLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "openai-llm", config })),
}));
jest.mock("../src/llms/openai_structured", () => ({
  OpenAIStructuredLLM: jest.fn().mockImplementation((config) => ({
    type: "openai-structured-llm",
    config,
  })),
}));
jest.mock("../src/llms/anthropic", () => ({
  AnthropicLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "anthropic-llm", config })),
}));
jest.mock("../src/llms/groq", () => ({
  GroqLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "groq-llm", config })),
}));
jest.mock("../src/llms/ollama", () => ({
  OllamaLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "ollama-llm", config })),
}));
jest.mock("../src/llms/google", () => ({
  GoogleLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "google-llm", config })),
}));
jest.mock("../src/llms/azure", () => ({
  AzureOpenAILLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "azure-llm", config })),
}));
jest.mock("../src/llms/mistral", () => ({
  MistralLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "mistral-llm", config })),
}));
jest.mock("../src/llms/langchain", () => ({
  LangchainLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "langchain-llm", config })),
}));
jest.mock("../src/llms/lmstudio", () => ({
  LMStudioLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "lmstudio-llm", config })),
}));
jest.mock("../src/llms/deepseek", () => ({
  DeepSeekLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "deepseek-llm", config })),
}));
jest.mock("../src/llms/xai", () => ({
  XAILLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "xai-llm", config })),
}));
jest.mock("../src/llms/sarvam", () => ({
  SarvamLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "sarvam-llm", config })),
}));
jest.mock("../src/llms/litellm", () => ({
  LiteLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "litellm-llm", config })),
}));
jest.mock("../src/llms/minimax", () => ({
  MiniMaxLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "minimax-llm", config })),
}));
jest.mock("../src/llms/together", () => ({
  TogetherLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "together-llm", config })),
}));
jest.mock("../src/llms/vllm", () => ({
  VllmLLM: jest
    .fn()
    .mockImplementation((config) => ({ type: "vllm-llm", config })),
}));

jest.mock("../src/vector_stores/qdrant", () => ({
  Qdrant: jest
    .fn()
    .mockImplementation((config) => ({ type: "qdrant", config })),
}));
jest.mock("../src/vector_stores/baidu", () => ({
  BaiduDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "baidu", config })),
}));
jest.mock("../src/vector_stores/redis", () => ({
  RedisDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "redis", config })),
}));
jest.mock("../src/vector_stores/valkey", () => ({
  ValkeyDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "valkey", config })),
}));
jest.mock("../src/vector_stores/supabase", () => ({
  SupabaseDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "supabase", config })),
}));
jest.mock("../src/vector_stores/langchain", () => ({
  LangchainVectorStore: jest
    .fn()
    .mockImplementation((config) => ({ type: "langchain-vs", config })),
}));
jest.mock("../src/vector_stores/vectorize", () => ({
  VectorizeDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "vectorize", config })),
}));
jest.mock("../src/vector_stores/azure_ai_search", () => ({
  AzureAISearch: jest
    .fn()
    .mockImplementation((config) => ({ type: "azure-ai-search", config })),
}));
jest.mock("../src/vector_stores/pgvector", () => ({
  PGVector: jest
    .fn()
    .mockImplementation((config) => ({ type: "pgvector", config })),
}));
jest.mock("../src/vector_stores/upstash_vector", () => ({
  UpstashVector: jest
    .fn()
    .mockImplementation((config) => ({ type: "upstash-vector", config })),
}));
jest.mock("../src/vector_stores/azure_mysql", () => ({
  AzureMySQLDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "azure_mysql", config })),
}));
jest.mock("../src/vector_stores/cassandra", () => ({
  CassandraDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "cassandra", config })),
}));
jest.mock("../src/vector_stores/s3_vectors", () => ({
  S3Vectors: jest
    .fn()
    .mockImplementation((config) => ({ type: "s3-vectors", config })),
}));
jest.mock("../src/vector_stores/weaviate", () => ({
  WeaviateDB: jest
    .fn()
    .mockImplementation((config) => ({ type: "weaviate", config })),
}));
jest.mock("../src/storage/SupabaseHistoryManager", () => ({
  SupabaseHistoryManager: jest
    .fn()
    .mockImplementation((config) => ({ type: "supabase-history", config })),
}));

import {
  EmbedderFactory,
  LLMFactory,
  VectorStoreFactory,
  HistoryManagerFactory,
} from "../src/utils/factory";
import type {
  EmbeddingConfig,
  LLMConfig,
  VectorStoreConfig,
  HistoryStoreConfig,
} from "../src/types";

const dummyEmbedConfig: EmbeddingConfig = { apiKey: "test" };
const dummyLLMConfig: LLMConfig = { apiKey: "test" };
const dummyVSConfig: VectorStoreConfig = {
  collectionName: "test",
  dimension: 1536,
};

// ─── EmbedderFactory ────────────────────────────────────

describe("EmbedderFactory", () => {
  test.each([
    ["openai"],
    ["ollama"],
    ["google"],
    ["gemini"],
    ["azure_openai"],
    ["fastembed"],
    ["langchain"],
    ["lmstudio"],
    ["vertexai"],
    ["together"],
  ])("creates embedder for provider '%s'", (provider) => {
    expect(() =>
      EmbedderFactory.create(provider, dummyEmbedConfig),
    ).not.toThrow();
  });

  test("is case-insensitive", () => {
    expect(() =>
      EmbedderFactory.create("OpenAI", dummyEmbedConfig),
    ).not.toThrow();
  });

  test("throws for unsupported provider", () => {
    expect(() =>
      EmbedderFactory.create("nonexistent", dummyEmbedConfig),
    ).toThrow("Unsupported embedder provider: nonexistent");
  });

  test("passes config to created embedder", () => {
    const config: EmbeddingConfig = { apiKey: "my-key", model: "my-model" };
    const result = EmbedderFactory.create("openai", config) as any;
    expect(result.config).toBe(config);
  });
});

// ─── LLMFactory ─────────────────────────────────────────

describe("LLMFactory", () => {
  test.each([
    ["openai"],
    ["openai_structured"],
    ["anthropic"],
    ["groq"],
    ["ollama"],
    ["google"],
    ["gemini"],
    ["azure_openai"],
    ["mistral"],
    ["langchain"],
    ["lmstudio"],
    ["deepseek"],
    ["xai"],
    ["sarvam"],
    ["litellm"],
    ["minimax"],
    ["together"],
    ["vllm"],
  ])("creates LLM for provider '%s'", (provider) => {
    expect(() => LLMFactory.create(provider, dummyLLMConfig)).not.toThrow();
  });

  test("is case-insensitive", () => {
    expect(() => LLMFactory.create("Anthropic", dummyLLMConfig)).not.toThrow();
  });

  test("throws for unsupported provider", () => {
    expect(() => LLMFactory.create("nonexistent", dummyLLMConfig)).toThrow(
      "Unsupported LLM provider: nonexistent",
    );
  });

  test("passes config to created LLM", () => {
    const config: LLMConfig = { apiKey: "my-key", model: "gpt-4" };
    const result = LLMFactory.create("openai", config) as any;
    expect(result.config).toBe(config);
  });
});

// ─── VectorStoreFactory ─────────────────────────────────

describe("VectorStoreFactory", () => {
  test("creates memory vector store", () => {
    // MemoryVectorStore is real (not mocked) — needs valid config
    expect(() =>
      VectorStoreFactory.create("memory", {
        collectionName: "test",
        dimension: 4,
        dbPath: ":memory:",
      }),
    ).not.toThrow();
  });

  test.each([
    ["baidu"],
    ["qdrant"],
    ["redis"],
    ["valkey"],
    ["supabase"],
    ["langchain"],
    ["vectorize"],
    ["azure-ai-search"],
    ["pgvector"],
    ["upstash_vector"],
    ["azure_mysql"],
    ["cassandra"],
    ["s3-vectors"],
    ["s3_vectors"],
    ["weaviate"],
  ])("creates vector store for provider '%s'", (provider) => {
    const result = VectorStoreFactory.create(provider, dummyVSConfig) as any;
    expect(result.config).toBe(dummyVSConfig);
  });

  test("throws for unsupported provider", () => {
    expect(() =>
      VectorStoreFactory.create("nonexistent", dummyVSConfig),
    ).toThrow("Unsupported vector store provider: nonexistent");
  });
});

// ─── HistoryManagerFactory ──────────────────────────────

describe("HistoryManagerFactory", () => {
  test("creates SQLite history manager", () => {
    const config: HistoryStoreConfig = {
      provider: "sqlite",
      config: { historyDbPath: ":memory:" },
    };
    expect(() => HistoryManagerFactory.create("sqlite", config)).not.toThrow();
  });

  test("creates supabase history manager", () => {
    const config: HistoryStoreConfig = {
      provider: "supabase",
      config: { supabaseUrl: "http://test", supabaseKey: "key" },
    };
    expect(() =>
      HistoryManagerFactory.create("supabase", config),
    ).not.toThrow();
  });

  test("creates memory history manager", () => {
    const config: HistoryStoreConfig = {
      provider: "memory",
      config: {},
    };
    expect(() => HistoryManagerFactory.create("memory", config)).not.toThrow();
  });

  test("throws for unsupported provider", () => {
    const config: HistoryStoreConfig = { provider: "bad", config: {} };
    expect(() => HistoryManagerFactory.create("bad", config)).toThrow(
      "Unsupported history store provider: bad",
    );
  });
});
