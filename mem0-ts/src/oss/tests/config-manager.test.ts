/// <reference types="jest" />
import { ConfigManager } from "../src/config/manager";

describe("ConfigManager", () => {
  describe("mergeConfig - dimension handling", () => {
    const baseLlm = {
      provider: "openai",
      config: { apiKey: "test-key" },
    };

    it("should leave dimension undefined when no explicit dimension or embeddingDims provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: { provider: "openai", config: { apiKey: "test-key" } },
        vectorStore: { provider: "memory", config: { collectionName: "test" } },
        llm: baseLlm,
      });

      // Dimension should be undefined so Memory._autoInitialize() will
      // auto-detect it via a probe embedding at runtime.
      expect(config.vectorStore.config.dimension).toBeUndefined();
    });

    it("should use embeddingDims from embedder config when provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });

    it("should prefer explicit vector store dimension over embedder dims", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", dimension: 1024 },
        },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(1024);
    });

    it("should leave dimension undefined when using a custom client without explicit dims", () => {
      const mockClient = { someMethod: () => {} };
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text" },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", client: mockClient },
        },
        llm: baseLlm,
      });

      // No embeddingDims and no explicit dimension → should be undefined
      // for auto-detection at runtime.
      expect(config.vectorStore.config.dimension).toBeUndefined();
    });

    it("should use embeddingDims when using a custom client", () => {
      const mockClient = { someMethod: () => {} };
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: { model: "nomic-embed-text", embeddingDims: 768 },
        },
        vectorStore: {
          provider: "qdrant",
          config: { collectionName: "test", client: mockClient },
        },
        llm: baseLlm,
      });

      expect(config.vectorStore.config.dimension).toBe(768);
    });
  });

  describe("mergeConfig - LLM url passthrough for Ollama", () => {
    const baseEmbedder = {
      provider: "openai",
      config: { apiKey: "test-key" },
    };
    const baseVectorStore = {
      provider: "memory",
      config: { collectionName: "test" },
    };

    it("should preserve url in LLM config when provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b", url: "http://10.0.0.100:11434" },
        },
      });

      expect(config.llm.config.url).toBe("http://10.0.0.100:11434");
    });

    it("should prefer baseURL over url when both are provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: {
            model: "llama3.2:3b",
            baseURL: "http://custom:11434",
            url: "http://fallback:11434",
          },
        },
      });

      expect(config.llm.config.baseURL).toBe("http://custom:11434");
      expect(config.llm.config.url).toBe("http://fallback:11434");
    });

    it("should use url as baseURL fallback when no baseURL provided (issue #4715)", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.1:8b", url: "http://my-ollama-host:11434" },
        },
      });

      expect(config.llm.config.baseURL).toBe("http://my-ollama-host:11434");
      expect(config.llm.config.url).toBe("http://my-ollama-host:11434");
    });

    it("should use default baseURL when no url or baseURL provided", () => {
      const config = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b" },
        },
      });

      expect(config.llm.config.url).toBeUndefined();
      expect(config.llm.config.baseURL).toBe("https://api.openai.com/v1");
    });

    it("should preserve url in embedder config (existing behavior)", () => {
      const config = ConfigManager.mergeConfig({
        embedder: {
          provider: "ollama",
          config: {
            model: "nomic-embed-text",
            url: "http://10.0.0.100:11434",
          },
        },
        vectorStore: baseVectorStore,
        llm: {
          provider: "ollama",
          config: { model: "llama3.2:3b", url: "http://10.0.0.100:11434" },
        },
      });

      expect(config.embedder.config.url).toBe("http://10.0.0.100:11434");
      expect(config.llm.config.url).toBe("http://10.0.0.100:11434");
    });
  });

  // ─────────────────────────────────────────────────────────────────────
  // LM Studio snake_case normalization
  // ─────────────────────────────────────────────────────────────────────
  describe("mergeConfig - LM Studio embedder config", () => {
    const baseLlm = { provider: "openai", config: { apiKey: "k" } };

    it("normalizes lmstudio_base_url to baseURL for embedder", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "nomic-embed-text-v1.5",
            lmstudio_base_url: "http://192.168.1.1:1234/v1",
          } as any,
        },
        vectorStore: { provider: "memory", config: {} },
        llm: baseLlm,
      });

      expect(cfg.embedder.provider).toBe("lmstudio");
      expect(cfg.embedder.config.baseURL).toBe("http://192.168.1.1:1234/v1");
      expect(cfg.embedder.config.model).toBe("nomic-embed-text-v1.5");
    });

    it("normalizes embedding_dims to embeddingDims for embedder", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "nomic-embed-text-v1.5",
            embedding_dims: 768,
          } as any,
        },
        vectorStore: { provider: "memory", config: {} },
        llm: baseLlm,
      });

      expect(cfg.embedder.config.embeddingDims).toBe(768);
    });

    it("prefers camelCase baseURL over snake_case lmstudio_base_url", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "test",
            baseURL: "http://camel:1234/v1",
            lmstudio_base_url: "http://snake:1234/v1",
          } as any,
        },
        vectorStore: { provider: "memory", config: {} },
        llm: baseLlm,
      });

      expect(cfg.embedder.config.baseURL).toBe("http://camel:1234/v1");
    });

    it("prefers camelCase embeddingDims over snake_case embedding_dims", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "test",
            embeddingDims: 1536,
            embedding_dims: 768,
          } as any,
        },
        vectorStore: { provider: "memory", config: {} },
        llm: baseLlm,
      });

      expect(cfg.embedder.config.embeddingDims).toBe(1536);
    });

    it("passes through camelCase config without issues", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "nomic-embed-text-v1.5",
            baseURL: "http://localhost:1234/v1",
            embeddingDims: 768,
          },
        },
        vectorStore: { provider: "memory", config: {} },
        llm: baseLlm,
      });

      expect(cfg.embedder.config.baseURL).toBe("http://localhost:1234/v1");
      expect(cfg.embedder.config.embeddingDims).toBe(768);
    });
  });

  describe("mergeConfig - LM Studio LLM config", () => {
    const baseEmbedder = { provider: "openai", config: { apiKey: "k" } };

    it("normalizes lmstudio_base_url to baseURL for LLM", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: { provider: "memory", config: {} },
        llm: {
          provider: "lmstudio",
          config: {
            model: "meta-llama-3.1",
            lmstudio_base_url: "http://192.168.1.1:1234/v1",
          } as any,
        },
      });

      expect(cfg.llm.provider).toBe("lmstudio");
      expect(cfg.llm.config.baseURL).toBe("http://192.168.1.1:1234/v1");
      expect(cfg.llm.config.model).toBe("meta-llama-3.1");
    });

    it("prefers camelCase baseURL over lmstudio_base_url for LLM", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: { provider: "memory", config: {} },
        llm: {
          provider: "lmstudio",
          config: {
            baseURL: "http://camel:1234/v1",
            lmstudio_base_url: "http://snake:1234/v1",
          } as any,
        },
      });

      expect(cfg.llm.config.baseURL).toBe("http://camel:1234/v1");
    });

    it("falls back to default baseURL when neither is provided for LLM", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: baseEmbedder,
        vectorStore: { provider: "memory", config: {} },
        llm: { provider: "lmstudio", config: { model: "test-model" } },
      });

      expect(cfg.llm.config.baseURL).toBe("https://api.openai.com/v1");
    });
  });

  describe("mergeConfig - full OpenClaw-style LM Studio config", () => {
    it("handles the exact config from issue #4235", () => {
      const cfg = ConfigManager.mergeConfig({
        embedder: {
          provider: "lmstudio",
          config: {
            model: "text-embedding-gte-qwen2-1.5b-instruct",
            embedding_dims: 1536,
            lmstudio_base_url: "http://192.168.200.83:1234/v1",
          } as any,
        },
        vectorStore: {
          provider: "qdrant",
          config: {
            host: "192.168.200.12",
            port: 6333,
            checkCompatibility: false,
          },
        },
        llm: {
          provider: "lmstudio",
          config: {
            model: "openai/gpt-oss-20b",
            lmstudio_base_url: "http://192.168.200.83:1234/v1",
          } as any,
        },
      });

      expect(cfg.embedder.provider).toBe("lmstudio");
      expect(cfg.embedder.config.baseURL).toBe("http://192.168.200.83:1234/v1");
      expect(cfg.embedder.config.model).toBe(
        "text-embedding-gte-qwen2-1.5b-instruct",
      );
      expect(cfg.embedder.config.embeddingDims).toBe(1536);

      expect(cfg.llm.provider).toBe("lmstudio");
      expect(cfg.llm.config.baseURL).toBe("http://192.168.200.83:1234/v1");
      expect(cfg.llm.config.model).toBe("openai/gpt-oss-20b");

      expect(cfg.vectorStore.provider).toBe("qdrant");
      expect(cfg.vectorStore.config.host).toBe("192.168.200.12");
      expect(cfg.vectorStore.config.port).toBe(6333);
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Memory class – LM Studio end-to-end flow (mocked factories)
// ─────────────────────────────────────────────────────────────────────────
describe("Memory – LM Studio end-to-end flow", () => {
  let MemoryClass: any;
  let mockEmbedderFactory: any;
  let mockVectorStoreFactory: any;
  let mockLlmFactory: any;
  let mockHistoryFactory: any;
  let mockEmbedder: any;
  let mockVStore: any;
  let mockLlm: any;

  beforeEach(() => {
    jest.resetModules();

    mockEmbedder = {
      embed: jest.fn().mockResolvedValue(new Array(768).fill(0.1)),
      embedBatch: jest.fn().mockResolvedValue([new Array(768).fill(0.1)]),
    };
    mockVStore = {
      insert: jest.fn().mockResolvedValue(undefined),
      search: jest.fn().mockResolvedValue([]),
      get: jest.fn().mockResolvedValue(null),
      update: jest.fn().mockResolvedValue(undefined),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCol: jest.fn().mockResolvedValue(undefined),
      list: jest.fn().mockResolvedValue([[], 0]),
      getUserId: jest.fn().mockResolvedValue("test-user-id"),
      setUserId: jest.fn().mockResolvedValue(undefined),
      initialize: jest.fn().mockResolvedValue(undefined),
    };
    mockLlm = {
      generateResponse: jest.fn().mockResolvedValue('{"facts":[]}'),
    };

    mockEmbedderFactory = { create: jest.fn().mockReturnValue(mockEmbedder) };
    mockVectorStoreFactory = { create: jest.fn().mockReturnValue(mockVStore) };
    mockLlmFactory = { create: jest.fn().mockReturnValue(mockLlm) };
    mockHistoryFactory = {
      create: jest.fn().mockReturnValue({
        addHistory: jest.fn().mockResolvedValue(undefined),
        getHistory: jest.fn().mockResolvedValue([]),
        reset: jest.fn().mockResolvedValue(undefined),
      }),
    };

    jest.doMock("../src/utils/factory", () => ({
      EmbedderFactory: mockEmbedderFactory,
      VectorStoreFactory: mockVectorStoreFactory,
      LLMFactory: mockLlmFactory,
      HistoryManagerFactory: mockHistoryFactory,
    }));
    jest.doMock("../src/utils/telemetry", () => ({
      captureClientEvent: jest.fn().mockResolvedValue(undefined),
    }));

    MemoryClass = require("../src/memory").Memory;
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.resetModules();
  });

  it("creates Memory with lmstudio embedder and llm providers", async () => {
    const mem = new MemoryClass({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
        },
      },
      vectorStore: { provider: "memory", config: { collectionName: "test" } },
      llm: {
        provider: "lmstudio",
        config: {
          model: "meta-llama-3.1-70b",
          baseURL: "http://localhost:1234/v1",
        },
      },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    expect(mockEmbedderFactory.create).toHaveBeenCalledWith(
      "lmstudio",
      expect.objectContaining({
        model: "nomic-embed-text-v1.5",
        baseURL: "http://localhost:1234/v1",
      }),
    );
    expect(mockLlmFactory.create).toHaveBeenCalledWith(
      "lmstudio",
      expect.objectContaining({
        model: "meta-llama-3.1-70b",
        baseURL: "http://localhost:1234/v1",
      }),
    );
  });

  it("auto-detects embedding dimension via probe with lmstudio", async () => {
    const mem = new MemoryClass({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
        },
      },
      vectorStore: { provider: "qdrant", config: { collectionName: "test" } },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    expect(mockEmbedder.embed).toHaveBeenCalledWith("dimension probe");
    const vsCall = mockVectorStoreFactory.create.mock.calls[0];
    expect(vsCall[1].dimension).toBe(768);
  });

  it("handles snake_case OpenClaw config through full Memory stack", async () => {
    const mem = new MemoryClass({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "text-embedding-gte-qwen2-1.5b-instruct",
          embedding_dims: 1536,
          lmstudio_base_url: "http://192.168.200.83:1234/v1",
        } as any,
      },
      vectorStore: { provider: "memory", config: { collectionName: "test" } },
      llm: {
        provider: "lmstudio",
        config: {
          model: "openai/gpt-oss-20b",
          lmstudio_base_url: "http://192.168.200.83:1234/v1",
        } as any,
      },
      disableHistory: true,
    });

    await mem.getAll({ filters: { user_id: "u1" } });

    expect(mockEmbedderFactory.create).toHaveBeenCalledWith(
      "lmstudio",
      expect.objectContaining({
        model: "text-embedding-gte-qwen2-1.5b-instruct",
        baseURL: "http://192.168.200.83:1234/v1",
      }),
    );
    expect(mockLlmFactory.create).toHaveBeenCalledWith(
      "lmstudio",
      expect.objectContaining({
        model: "openai/gpt-oss-20b",
        baseURL: "http://192.168.200.83:1234/v1",
      }),
    );
  });

  it("search flow works with lmstudio embedder", async () => {
    mockVStore.search.mockResolvedValueOnce([
      {
        id: "mem-1",
        payload: {
          data: "User likes hiking",
          user_id: "u1",
          hash: "abc123",
          created_at: "2026-01-01",
        },
        score: 0.95,
      },
    ]);

    const mem = new MemoryClass({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: { baseURL: "http://localhost:1234/v1" },
      },
      disableHistory: true,
    });

    const result = await mem.search("What does the user like?", {
      filters: { user_id: "u1" },
    });

    expect(mockEmbedder.embed).toHaveBeenCalledWith("What does the user like?");
    expect(mockVStore.search).toHaveBeenCalled();
    expect(result.results).toHaveLength(1);
    expect(result.results[0].memory).toBe("User likes hiking");
  });

  it("add flow works with lmstudio LLM for fact extraction", async () => {
    mockLlm.generateResponse.mockResolvedValueOnce(
      '{"facts":["User loves sushi"]}',
    );
    mockVStore.search.mockResolvedValue([]);
    mockVStore.list.mockResolvedValue([[], 0]);

    const mem = new MemoryClass({
      embedder: {
        provider: "lmstudio",
        config: {
          model: "nomic-embed-text-v1.5",
          baseURL: "http://localhost:1234/v1",
          embeddingDims: 768,
        },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 768 },
      },
      llm: {
        provider: "lmstudio",
        config: {
          model: "meta-llama-3.1-70b",
          baseURL: "http://localhost:1234/v1",
        },
      },
      disableHistory: true,
    });

    await mem.add("I love sushi", { userId: "u1" });

    expect(mockLlm.generateResponse).toHaveBeenCalled();
    expect(mockEmbedder.embed).toHaveBeenCalled();
  });
});
