import { OpenAIEmbedder } from "../embeddings/openai";
import { AWSBedrockEmbedder } from "../embeddings/aws_bedrock";
import { OllamaEmbedder } from "../embeddings/ollama";
import { LMStudioEmbedder } from "../embeddings/lmstudio";
import { TogetherEmbedder } from "../embeddings/together";
import { OpenAILLM } from "../llms/openai";
import { OpenAIStructuredLLM } from "../llms/openai_structured";
import { AnthropicLLM } from "../llms/anthropic";
import { GroqLLM } from "../llms/groq";
import { MistralLLM } from "../llms/mistral";
import { MemoryVectorStore } from "../vector_stores/memory";
import {
  EmbeddingConfig,
  HistoryStoreConfig,
  LLMConfig,
  RerankerConfig,
  VectorStoreConfig,
} from "../types";
import { Reranker } from "../rerankers/base";
import { CohereReranker } from "../rerankers/cohere";
import { LLMReranker } from "../rerankers/llm";
import { ZeroEntropyReranker } from "../rerankers/zeroentropy";
import { CrossEncoderReranker } from "../rerankers/cross_encoder";
import { Embedder } from "../embeddings/base";
import { LLM } from "../llms/base";
import { VectorStore } from "../vector_stores/base";
import { BaiduDB } from "../vector_stores/baidu";
import { Qdrant } from "../vector_stores/qdrant";
import { ChromaDB } from "../vector_stores/chroma";
import { VectorizeDB } from "../vector_stores/vectorize";
import { RedisDB } from "../vector_stores/redis";
import { ValkeyDB } from "../vector_stores/valkey";
import { OllamaLLM } from "../llms/ollama";
import { LMStudioLLM } from "../llms/lmstudio";
import { DeepSeekLLM } from "../llms/deepseek";
import { XAILLM } from "../llms/xai";
import { SarvamLLM } from "../llms/sarvam";
import { LiteLLM } from "../llms/litellm";
import { MiniMaxLLM } from "../llms/minimax";
import { TogetherLLM } from "../llms/together";
import { VllmLLM } from "../llms/vllm";
import { SupabaseDB } from "../vector_stores/supabase";
import { SQLiteManager } from "../storage/SQLiteManager";
import { MemoryHistoryManager } from "../storage/MemoryHistoryManager";
import { SupabaseHistoryManager } from "../storage/SupabaseHistoryManager";
import { HistoryManager } from "../storage/base";
import { GoogleEmbedder } from "../embeddings/google";
import { GoogleLLM } from "../llms/google";
import { AzureOpenAILLM } from "../llms/azure";
import { AzureOpenAIEmbedder } from "../embeddings/azure";
import { FastEmbedEmbedder } from "../embeddings/fastembed";
import { LangchainLLM } from "../llms/langchain";
import { LangchainEmbedder } from "../embeddings/langchain";
import { HuggingFaceEmbedder } from "../embeddings/huggingface";
import { LangchainVectorStore } from "../vector_stores/langchain";
import { AzureAISearch } from "../vector_stores/azure_ai_search";
import { PGVector } from "../vector_stores/pgvector";
import { VertexAIEmbedder } from "../embeddings/vertexai";
import { ElasticsearchDB } from "../vector_stores/elasticsearch";
import { OpenSearchDB } from "../vector_stores/opensearch";
import { UpstashVector } from "../vector_stores/upstash_vector";
import { AzureMySQLDB } from "../vector_stores/azure_mysql";
import { VertexAIVectorSearch } from "../vector_stores/vertex_ai_vector_search";
import { CassandraDB } from "../vector_stores/cassandra";
import { PineconeDB } from "../vector_stores/pinecone";
import { S3Vectors } from "../vector_stores/s3_vectors";
import { TurbopufferDB } from "../vector_stores/turbopuffer";
import { Milvus } from "../vector_stores/milvus";
import { MongoDB } from "../vector_stores/mongodb";
import { WeaviateDB } from "../vector_stores/weaviate";

export class EmbedderFactory {
  static create(provider: string, config: EmbeddingConfig): Embedder {
    switch (provider.toLowerCase()) {
      case "openai":
        return new OpenAIEmbedder(config);
      case "aws_bedrock":
        return new AWSBedrockEmbedder(config);
      case "ollama":
        return new OllamaEmbedder(config);
      case "lmstudio":
        return new LMStudioEmbedder(config);
      case "together":
        return new TogetherEmbedder(config);
      case "google":
      case "gemini":
        return new GoogleEmbedder(config);
      case "azure_openai":
        return new AzureOpenAIEmbedder(config);
      case "fastembed":
        return new FastEmbedEmbedder(config);
      case "langchain":
        return new LangchainEmbedder(config);
      case "vertexai":
        return new VertexAIEmbedder(config);
      case "huggingface":
        return new HuggingFaceEmbedder(config);
      default:
        throw new Error(`Unsupported embedder provider: ${provider}`);
    }
  }
}

export class LLMFactory {
  static create(provider: string, config: LLMConfig): LLM {
    switch (provider.toLowerCase()) {
      case "openai":
        return new OpenAILLM(config);
      case "openai_structured":
        return new OpenAIStructuredLLM(config);
      case "anthropic":
        return new AnthropicLLM(config);
      case "groq":
        return new GroqLLM(config);
      case "ollama":
        return new OllamaLLM(config);
      case "lmstudio":
        return new LMStudioLLM(config);
      case "google":
      case "gemini":
        return new GoogleLLM(config);
      case "azure_openai":
        return new AzureOpenAILLM(config);
      case "mistral":
        return new MistralLLM(config);
      case "langchain":
        return new LangchainLLM(config);
      case "deepseek":
        return new DeepSeekLLM(config);
      case "xai":
        return new XAILLM(config);
      case "sarvam":
        return new SarvamLLM(config);
      case "litellm":
        return new LiteLLM(config);
      case "minimax":
        return new MiniMaxLLM(config);
      case "together":
        return new TogetherLLM(config);
      case "vllm":
        return new VllmLLM(config);
      default:
        throw new Error(`Unsupported LLM provider: ${provider}`);
    }
  }
}

export class VectorStoreFactory {
  static create(provider: string, config: VectorStoreConfig): VectorStore {
    switch (provider.toLowerCase()) {
      case "memory":
        return new MemoryVectorStore(config);
      case "baidu":
        return new BaiduDB(config as any);
      case "qdrant":
        return new Qdrant(config as any);
      case "chroma":
        return new ChromaDB(config as any);
      case "redis":
        return new RedisDB(config as any);
      case "valkey":
        return new ValkeyDB(config as any);
      case "supabase":
        return new SupabaseDB(config as any);
      case "langchain":
        return new LangchainVectorStore(config as any);
      case "vectorize":
        return new VectorizeDB(config as any);
      case "azure-ai-search":
        return new AzureAISearch(config as any);
      case "vertex_ai_vector_search":
        return new VertexAIVectorSearch(config as any);
      case "pgvector":
        return new PGVector(config as any);
      case "elasticsearch":
        return new ElasticsearchDB(config as any);
      case "opensearch":
        return new OpenSearchDB(config as any);
      case "upstash_vector":
        return new UpstashVector(config as any);
      case "azure_mysql":
        return new AzureMySQLDB(config as any);
      case "cassandra":
        return new CassandraDB(config as any);
      case "pinecone":
        return new PineconeDB(config as any);
      case "s3-vectors":
      case "s3_vectors":
        return new S3Vectors(config as any);
      case "turbopuffer":
        return new TurbopufferDB(config as any);
      case "milvus":
        return new Milvus(config as any);
      case "mongodb":
        return new MongoDB(config as any);
      case "weaviate":
        return new WeaviateDB(config as any);
      default:
        throw new Error(`Unsupported vector store provider: ${provider}`);
    }
  }
}

export class RerankerFactory {
  static create(provider: string, config: RerankerConfig): Reranker {
    switch (provider.toLowerCase()) {
      case "cohere":
        return new CohereReranker(config);
      case "zero_entropy":
        return new ZeroEntropyReranker(config);
      case "sentence_transformer":
        return new CrossEncoderReranker(
          config,
          "Xenova/ms-marco-MiniLM-L-6-v2",
        );
      case "huggingface":
        return new CrossEncoderReranker(
          config,
          "Xenova/bge-reranker-base",
          512,
        );
      case "llm_reranker": {
        const llm = RerankerFactory.buildLLMRerankerLLM(config);
        return new LLMReranker(config, llm);
      }
      default:
        throw new Error(`Unsupported reranker provider: ${provider}`);
    }
  }

  private static buildLLMRerankerLLM(config: RerankerConfig): LLM {
    const nested = config.llm;
    let llmProvider: string;
    let llmConfig: LLMConfig;

    if (nested) {
      llmProvider = nested.provider || config.provider || "openai";
      llmConfig = { ...(nested.config || {}) };
      if (llmConfig.model === undefined) {
        llmConfig.model = config.model ?? "gpt-4o-mini";
      }
      if (llmConfig.temperature === undefined) {
        llmConfig.temperature = config.temperature ?? 0.0;
      }
      if (llmConfig.maxTokens === undefined) {
        llmConfig.maxTokens = config.maxTokens ?? 100;
      }
      if (config.apiKey && llmConfig.apiKey === undefined) {
        llmConfig.apiKey = config.apiKey;
      }
    } else {
      llmProvider = config.provider || "openai";
      llmConfig = {
        model: config.model ?? "gpt-4o-mini",
        temperature: config.temperature ?? 0.0,
        maxTokens: config.maxTokens ?? 100,
      };
      if (config.apiKey) {
        llmConfig.apiKey = config.apiKey;
      }
    }

    return LLMFactory.create(llmProvider, llmConfig);
  }
}

export class HistoryManagerFactory {
  static create(provider: string, config: HistoryStoreConfig): HistoryManager {
    switch (provider.toLowerCase()) {
      case "sqlite":
        return new SQLiteManager(config.config.historyDbPath || ":memory:");
      case "supabase":
        return new SupabaseHistoryManager({
          supabaseUrl: config.config.supabaseUrl || "",
          supabaseKey: config.config.supabaseKey || "",
          tableName: config.config.tableName || "memory_history",
        });
      case "memory":
        return new MemoryHistoryManager();
      default:
        throw new Error(`Unsupported history store provider: ${provider}`);
    }
  }
}
