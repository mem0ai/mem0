import { MemoryConfig, MemoryConfigSchema } from "../types";
import { DEFAULT_MEMORY_CONFIG } from "./defaults";

export class ConfigManager {
  static mergeConfig(userConfig: Partial<MemoryConfig> = {}): MemoryConfig {
    const embedderProvider =
      userConfig.embedder?.provider || DEFAULT_MEMORY_CONFIG.embedder.provider;
    const embedderProviderKey = embedderProvider.toLowerCase();
    const mergedConfig = {
      version: userConfig.version || DEFAULT_MEMORY_CONFIG.version,
      embedder: {
        provider: embedderProvider,
        config: (() => {
          const defaultConf = DEFAULT_MEMORY_CONFIG.embedder.config;
          const userConf = userConfig.embedder?.config;
          // The default embedder model (OpenAI's text-embedding-3-small) only
          // makes sense for API-based providers. FastEmbed has its own fixed
          // model set and default, so leave the model unset here and let
          // FastEmbedEmbedder fall back to its own default.
          let finalModel: string | any =
            embedderProviderKey === "fastembed" ? undefined : defaultConf.model;

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
            // Spread first so provider-specific keys (e.g. the Vertex AI
            // project/location/credentials) survive the merge, while the
            // normalized values below still win.
            ...userConf,
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
        // Every factory already matches the provider case-insensitively, so a capitalized
        // name constructs the right store -- but the `provider === "memory"` comparisons that
        // pick per-provider entity-store settings do not. Normalize once, here, so those
        // comparisons cannot silently miss.
        provider: (
          userConfig.vectorStore?.provider ||
          DEFAULT_MEMORY_CONFIG.vectorStore.provider
        ).toLowerCase(),
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
          const provider =
            userConfig.llm?.provider || DEFAULT_MEMORY_CONFIG.llm.provider;
          let finalModel: string | any = defaultConf.model;

          if (userConf?.model && typeof userConf.model === "object") {
            finalModel = userConf.model;
          } else if (userConf?.model && typeof userConf.model === "string") {
            finalModel = userConf.model;
          }

          // Normalize snake_case keys from Python SDK / OpenClaw configs
          const llmRaw = userConf as Record<string, unknown> | undefined;
          const llmBaseURL =
            userConf?.baseURL ??
            userConf?.vllmBaseURL ??
            (llmRaw?.vllm_base_url as string | undefined) ??
            ((userConf as Record<string, unknown>)?.lmstudio_base_url as
              | string
              | undefined) ??
            userConf?.url ??
            (provider.toLowerCase() === "vllm"
              ? undefined
              : defaultConf.baseURL);
          const temperature =
            userConf?.temperature ??
            (llmRaw?.temperature as number | undefined);
          const topP = userConf?.topP ?? (llmRaw?.top_p as number | undefined);
          const maxTokens =
            userConf?.maxTokens ?? (llmRaw?.max_tokens as number | undefined);

          return {
            // Spread user-provided config first so any additional fields
            // (e.g. future aws_bedrock options) pass through without a
            // manager.ts edit, matching the vectorStore.config pattern above
            // and making the schema's .passthrough() on llm.config meaningful.
            ...userConf,
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
            temperature,
            topP,
            maxTokens,
            // Pass through AWS Bedrock fields so the aws_bedrock provider works
            // through the standard Memory config path (snake_case tolerated).
            awsRegion:
              userConf?.awsRegion ?? (llmRaw?.aws_region as string | undefined),
            awsAccessKeyId:
              userConf?.awsAccessKeyId ??
              (llmRaw?.aws_access_key_id as string | undefined),
            awsSecretAccessKey:
              userConf?.awsSecretAccessKey ??
              (llmRaw?.aws_secret_access_key as string | undefined),
            awsSessionToken:
              userConf?.awsSessionToken ??
              (llmRaw?.aws_session_token as string | undefined),
            client: userConf?.client,
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
      reranker: userConfig.reranker,
    };

    // Validate the merged config
    return MemoryConfigSchema.parse(mergedConfig);
  }
}
