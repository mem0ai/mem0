type ProviderConfig = {
  provider?: string;
  config?: {
    model?: string;
    api_key?: string;
  };
};

export type EffectiveConfig = {
  llm?: ProviderConfig;
  embedder?: ProviderConfig;
};

export const getEffectiveConfig = (data: unknown): EffectiveConfig | null => {
  if (!data || typeof data !== "object") {
    return null;
  }

  const record = data as Record<string, unknown>;
  return (
    (record.effective_config as EffectiveConfig) ||
    (record.config as EffectiveConfig) ||
    (record as EffectiveConfig)
  );
};

export const buildProviderConfig = ({
  provider,
  model,
  apiKey,
}: {
  provider: string;
  model: string;
  apiKey?: string;
}) => {
  if (!provider) {
    return undefined;
  }

  return {
    provider,
    config: {
      model: model || undefined,
      api_key: apiKey || undefined,
    },
  };
};
