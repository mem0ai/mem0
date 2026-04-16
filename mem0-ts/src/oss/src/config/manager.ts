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

          // Normalize snake_case keys from Python SDK / OpenClaw configs
          const baseURL =
            userConf?.baseURL ??
            ((userConf as Record<string, unknown>)?.lmstudio_base_url as
              | string
              | undefined) ??
            userConf?.url;
          const embeddingDims =
            userConf?.embeddingDims ??
            ((userConf as Record<string, unknown>)?.embedding_dims as
              | number
              | undefined);

          return {
            apiKey:
              userConf?.apiKey !== undefined
                ? userConf.apiKey
                : defaultConf.apiKey,
            model: finalModel,
            baseURL,
            url: userConf?.url,
            embeddingDims,
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

          // Resolve the vector store dimension.  If the user explicitly
          // provided one, use it.  Otherwise leave it undefined so that
          // Memory._autoInitialize() can auto-detect it by running a
          // probe embedding at startup — this makes *any* embedder work
          // out of the box without the user needing to know or set the
          // dimension manually.
          const explicitDimension =
            userConf?.dimension ||
            userConfig.embedder?.config?.embeddingDims ||
            undefined;

          // Prioritize user-provided client instance
          if (userConf?.client && typeof userConf.client === "object") {
            return {
              client: userConf.client,
              collectionName: userConf.collectionName,
              dimension: explicitDimension,
              ...userConf, // Include any other passthrough fields from user
            };
          } else {
            // If no client provided, merge standard fields
            return {
              collectionName:
                userConf?.collectionName || defaultConf.collectionName,
              dimension: explicitDimension,
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

          // Normalize snake_case keys from Python SDK / OpenClaw configs
          const llmBaseURL =
            userConf?.baseURL ??
            ((userConf as Record<string, unknown>)?.lmstudio_base_url as
              | string
              | undefined) ??
            userConf?.url ??
            defaultConf.baseURL;

          return {
            baseURL: llmBaseURL,
            url: userConf?.url,
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
        userConfig.historyDbPath ||
        userConfig.historyStore?.config?.historyDbPath ||
        DEFAULT_MEMORY_CONFIG.historyStore?.config?.historyDbPath,
      customInstructions: userConfig.customInstructions,
      historyStore: (() => {
        const defaultHistoryStore = DEFAULT_MEMORY_CONFIG.historyStore!;
        const historyProvider =
          userConfig.historyStore?.provider || defaultHistoryStore.provider;
        const isSqlite = historyProvider.toLowerCase() === "sqlite";

        // Precedence: explicit historyStore.config > top-level historyDbPath > default
        return {
          ...defaultHistoryStore,
          ...userConfig.historyStore,
          provider: historyProvider,
          config: {
            ...(isSqlite ? defaultHistoryStore.config : {}),
            ...(isSqlite && userConfig.historyDbPath
              ? { historyDbPath: userConfig.historyDbPath }
              : {}),
            ...userConfig.historyStore?.config,
          },
        };
      })(),
      disableHistory:
        userConfig.disableHistory || DEFAULT_MEMORY_CONFIG.disableHistory,
    };

    // Validate the merged config
    return MemoryConfigSchema.parse(mergedConfig);
  }
}
