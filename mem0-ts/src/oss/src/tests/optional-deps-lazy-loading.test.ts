const OPTIONAL_MODULES = [
  "better-sqlite3",
  "@anthropic-ai/sdk",
  "@google/genai",
  "groq-sdk",
  "ollama",
  "@mistralai/mistralai",
  "@qdrant/js-client-rest",
  "redis",
  "@supabase/supabase-js",
  "pg",
  "cloudflare",
  "@azure/identity",
  "@azure/search-documents",
  "neo4j-driver",
];

const OPENAI_LLM_CONFIG = {
  apiKey: "test-key",
  model: "gpt-4.1-nano-2025-04-14",
};

async function withMissingModules<T>(
  modules: string[],
  fn: () => T | Promise<T>,
): Promise<T> {
  jest.resetModules();
  for (const moduleName of modules) {
    jest.doMock(
      moduleName,
      () => {
        const err = new Error(`Cannot find module '${moduleName}'`) as Error & {
          code?: string;
        };
        err.code = "MODULE_NOT_FOUND";
        throw err;
      },
      { virtual: true },
    );
  }

  try {
    return await fn();
  } finally {
    for (const moduleName of modules) {
      jest.dontMock(moduleName);
    }
    jest.resetModules();
  }
}

function assertUnrelatedProviderStillWorks(): void {
  const { LLMFactory } = require("../utils/factory");
  expect(() => LLMFactory.create("openai", OPENAI_LLM_CONFIG)).not.toThrow();
}

type ProviderCase = {
  name: string;
  packageName: string;
  selectProvider: () => void;
};

const providerCases: ProviderCase[] = [
  {
    name: "sqlite history provider",
    packageName: "better-sqlite3",
    selectProvider: () => {
      const { HistoryManagerFactory } = require("../utils/factory");
      HistoryManagerFactory.create("sqlite", {
        provider: "sqlite",
        config: { historyDbPath: ":memory:" },
      });
    },
  },
  {
    name: "memory vector store provider",
    packageName: "better-sqlite3",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("memory", { dimension: 3 });
    },
  },
  {
    name: "qdrant vector store provider",
    packageName: "@qdrant/js-client-rest",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("qdrant", {
        collectionName: "memories",
        dimension: 3,
        path: "/tmp/mem0-qdrant",
      });
    },
  },
  {
    name: "redis vector store provider",
    packageName: "redis",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("redis", {
        collectionName: "memories",
        redisUrl: "redis://127.0.0.1:6379",
        embeddingModelDims: 3,
      });
    },
  },
  {
    name: "supabase vector store provider",
    packageName: "@supabase/supabase-js",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("supabase", {
        tableName: "memories",
        supabaseUrl: "https://example.supabase.co",
        supabaseKey: "test-key",
      });
    },
  },
  {
    name: "pgvector provider",
    packageName: "pg",
    selectProvider: () => {
      const { PGVector } = require("../vector_stores/pgvector");
      new PGVector({
        collectionName: "memories",
        user: "postgres",
        password: "postgres",
        host: "127.0.0.1",
        port: 5432,
        embeddingModelDims: 3,
      });
    },
  },
  {
    name: "cloudflare vectorize provider",
    packageName: "cloudflare",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("vectorize", {
        apiKey: "test-token",
        accountId: "account-id",
        indexName: "index-name",
        dimension: 3,
      });
    },
  },
  {
    name: "azure ai search provider (search-documents package)",
    packageName: "@azure/search-documents",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("azure-ai-search", {
        serviceName: "test-service",
        collectionName: "test-index",
        embeddingModelDims: 3,
        apiKey: "test-api-key",
      });
    },
  },
  {
    name: "azure ai search provider (identity package)",
    packageName: "@azure/identity",
    selectProvider: () => {
      const { VectorStoreFactory } = require("../utils/factory");
      VectorStoreFactory.create("azure-ai-search", {
        serviceName: "test-service",
        collectionName: "test-index",
        embeddingModelDims: 3,
        apiKey: "test-api-key",
      });
    },
  },
  {
    name: "neo4j graph provider",
    packageName: "neo4j-driver",
    selectProvider: () => {
      const { MemoryGraph } = require("../memory/graph_memory");
      new MemoryGraph({
        embedder: {
          provider: "openai",
          config: { apiKey: "test-key", model: "text-embedding-3-small" },
        },
        llm: {
          provider: "openai",
          config: OPENAI_LLM_CONFIG,
        },
        vectorStore: {
          provider: "memory",
          config: { dimension: 3 },
        },
        enableGraph: true,
        graphStore: {
          provider: "neo4j",
          config: {
            url: "neo4j://localhost:7687",
            username: "neo4j",
            password: "password",
          },
        },
      });
    },
  },
  {
    name: "anthropic llm provider",
    packageName: "@anthropic-ai/sdk",
    selectProvider: () => {
      const { LLMFactory } = require("../utils/factory");
      LLMFactory.create("anthropic", {
        apiKey: "test-key",
        model: "claude-3-sonnet-20240229",
      });
    },
  },
  {
    name: "google llm provider",
    packageName: "@google/genai",
    selectProvider: () => {
      const { LLMFactory } = require("../utils/factory");
      LLMFactory.create("google", {
        apiKey: "test-key",
        model: "gemini-2.0-flash",
      });
    },
  },
  {
    name: "groq llm provider",
    packageName: "groq-sdk",
    selectProvider: () => {
      const { LLMFactory } = require("../utils/factory");
      LLMFactory.create("groq", {
        apiKey: "test-key",
        model: "llama3-70b-8192",
      });
    },
  },
  {
    name: "ollama llm provider",
    packageName: "ollama",
    selectProvider: () => {
      const { LLMFactory } = require("../utils/factory");
      LLMFactory.create("ollama", {
        model: "llama3.1:8b",
        url: "http://localhost:11434",
      });
    },
  },
  {
    name: "mistral llm provider",
    packageName: "@mistralai/mistralai",
    selectProvider: () => {
      const { LLMFactory } = require("../utils/factory");
      LLMFactory.create("mistral", {
        apiKey: "test-key",
        model: "mistral-tiny-latest",
      });
    },
  },
];

describe("optional dependency lazy-loading", () => {
  it("does not load optional dependencies when importing OSS entrypoint", async () => {
    await expect(
      withMissingModules(OPTIONAL_MODULES, () => {
        jest.isolateModules(() => {
          require("../index");
        });
      }),
    ).resolves.toBeUndefined();
  });

  it.each(providerCases)(
    "throws install hint only when selected provider is used: $name",
    async ({ packageName, selectProvider }) => {
      await expect(
        withMissingModules([packageName], () => {
          jest.isolateModules(() => {
            require("../index");
            assertUnrelatedProviderStillWorks();
            expect(() => selectProvider()).toThrow(
              `Install optional dependency '${packageName}'`,
            );
          });
        }),
      ).resolves.toBeUndefined();
    },
  );

  it("does not fail for disableHistory=true with non-sqlite vector store", async () => {
    await withMissingModules(["better-sqlite3"], async () => {
      let MemoryCtor: any;
      jest.isolateModules(() => {
        ({ Memory: MemoryCtor } = require("../memory"));
      });

      const memory = new MemoryCtor({
        disableHistory: true,
        embedder: {
          provider: "openai",
          config: { apiKey: "test-key", model: "text-embedding-3-small" },
        },
        llm: {
          provider: "openai",
          config: { apiKey: "test-key", model: "gpt-4.1-nano-2025-04-14" },
        },
        vectorStore: {
          provider: "langchain",
          config: {
            dimension: 3,
            client: {
              addVectors: async () => undefined,
              similaritySearchVectorWithScore: async () => [],
            },
          },
        },
      });

      await expect(
        (memory as any)._ensureInitialized(),
      ).resolves.toBeUndefined();
    });
  });
});
