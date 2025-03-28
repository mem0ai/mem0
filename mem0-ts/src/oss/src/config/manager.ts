import { MemoryConfig, MemoryConfigSchema } from "../types";
import { DEFAULT_MEMORY_CONFIG } from "./defaults";

export class ConfigManager {
  static mergeConfig(userConfig: Partial<MemoryConfig> = {}): MemoryConfig {
    const mergedConfig = {
      version: userConfig.version || DEFAULT_MEMORY_CONFIG.version,
      embedder: {
        provider:
          userConfig.embedder?.provider ||
          DEFAULT_MEMORY_CONFIG.embedder.provider,
        config: {
          apiKey:
            userConfig.embedder?.config?.apiKey ||
            DEFAULT_MEMORY_CONFIG.embedder.config.apiKey,
          model:
            userConfig.embedder?.config?.model ||
            DEFAULT_MEMORY_CONFIG.embedder.config.model,
        },
      },
      vectorStore: {
        provider:
          userConfig.vectorStore?.provider ||
          DEFAULT_MEMORY_CONFIG.vectorStore.provider,
        config: {
          collectionName:
            userConfig.vectorStore?.config?.collectionName ||
            DEFAULT_MEMORY_CONFIG.vectorStore.config.collectionName,
          dimension:
            userConfig.vectorStore?.config?.dimension ||
            DEFAULT_MEMORY_CONFIG.vectorStore.config.dimension,
          ...userConfig.vectorStore?.config,
        },
      },
      llm: {
        provider:
          userConfig.llm?.provider || DEFAULT_MEMORY_CONFIG.llm.provider,
        config: {
          apiKey:
            userConfig.llm?.config?.apiKey ||
            DEFAULT_MEMORY_CONFIG.llm.config.apiKey,
          model:
            userConfig.llm?.config?.model ||
            DEFAULT_MEMORY_CONFIG.llm.config.model,
        },
      },
      historyDbPath:
        userConfig.historyDbPath || DEFAULT_MEMORY_CONFIG.historyDbPath,
      customPrompt: userConfig.customPrompt,
      graphStore: {
        ...DEFAULT_MEMORY_CONFIG.graphStore,
        ...userConfig.graphStore,
      },
      historyStore: {
        ...DEFAULT_MEMORY_CONFIG.historyStore,
        ...userConfig.historyStore,
      },
      disableHistory:
        userConfig.disableHistory || DEFAULT_MEMORY_CONFIG.disableHistory,
      enableGraph: userConfig.enableGraph || DEFAULT_MEMORY_CONFIG.enableGraph,
    };

    // Validate the merged config
    return MemoryConfigSchema.parse(mergedConfig);
  }
}
