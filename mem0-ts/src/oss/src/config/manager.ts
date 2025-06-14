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
        config: (() => {
          const defaultConf = DEFAULT_MEMORY_CONFIG.embedder.config;
          const userConf = userConfig.embedder?.config;
          let finalModel: string | any = defaultConf.model;

          if (userConf?.model && typeof userConf.model === "object") {
            finalModel = userConf.model;
          } else if (userConf?.model && typeof userConf.model === "string") {
            finalModel = userConf.model;
          }

          return {
            apiKey:
              userConf?.apiKey !== undefined
                ? userConf.apiKey
                : defaultConf.apiKey,
            model: finalModel,
            url: userConf?.url,
            modelProperties:
              userConf?.modelProperties !== undefined
                ? userConf.modelProperties
                : defaultConf.modelProperties,
          };
        })(),
      },
      vectorStore: {
        provider:
          userConfig.vectorStore?.provider ||
          DEFAULT_MEMORY_CONFIG.vectorStore.provider,
        config: (() => {
          const defaultConf = DEFAULT_MEMORY_CONFIG.vectorStore.config;
          const userConf = userConfig.vectorStore?.config;

          // Prioritize user-provided client instance
          if (userConf?.client && typeof userConf.client === "object") {
            return {
              client: userConf.client,
              // Include other fields from userConf if necessary, or omit defaults
              collectionName: userConf.collectionName, // Can be undefined
              dimension: userConf.dimension || defaultConf.dimension, // Merge dimension
              ...userConf, // Include any other passthrough fields from user
            };
          } else {
            // If no client provided, merge standard fields
            return {
              collectionName:
                userConf?.collectionName || defaultConf.collectionName,
              dimension: userConf?.dimension || defaultConf.dimension,
              // Ensure client is not carried over from defaults if not provided by user
              client: undefined,
              // Include other passthrough fields from userConf even if no client
              ...userConf,
            };
          }
        })(),
      },
      llm: {
        provider:
          userConfig.llm?.provider || DEFAULT_MEMORY_CONFIG.llm.provider,
        config: (() => {
          const defaultConf = DEFAULT_MEMORY_CONFIG.llm.config;
          const userConf = userConfig.llm?.config;
          let finalModel: string | any = defaultConf.model;

          if (userConf?.model && typeof userConf.model === "object") {
            finalModel = userConf.model;
          } else if (userConf?.model && typeof userConf.model === "string") {
            finalModel = userConf.model;
          }

          return {
            baseURL: userConf?.baseURL || defaultConf.baseURL,
            apiKey:
              userConf?.apiKey !== undefined
                ? userConf.apiKey
                : defaultConf.apiKey,
            model: finalModel,
            modelProperties:
              userConf?.modelProperties !== undefined
                ? userConf.modelProperties
                : defaultConf.modelProperties,
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
