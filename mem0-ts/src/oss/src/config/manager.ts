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
        config: (() => {
          const defaultConf = DEFAULT_MEMORY_CONFIG.llm.config;
          const userConf = userConfig.llm?.config;
          let finalModel: string | any = defaultConf.model;

          // If user provides a model and it's an object, use it as the instance
          if (userConf?.model && typeof userConf.model === "object") {
            finalModel = userConf.model;
          } else if (userConf?.model && typeof userConf.model === "string") {
            // If user provides a string model name, use it
            finalModel = userConf.model;
          } // Otherwise, finalModel retains the default string name

          return {
            apiKey:
              userConf?.apiKey !== undefined
                ? userConf.apiKey
                : defaultConf.apiKey,
            model: finalModel,
            modelProperties:
              userConf?.modelProperties !== undefined
                ? userConf.modelProperties
                : defaultConf.modelProperties,
            // Add other potential config fields here if needed in the future
          };
        })(),
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
