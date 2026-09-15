type ProviderConfig = {
  provider?: string;
  config?: {
    model?: string;
    api_key?: string;
    api_key_set?: boolean;
    openai_base_url?: string;
  };
};

export type EffectiveConfig = {
  llm?: ProviderConfig;
  embedder?: ProviderConfig;
};

export const hasConfiguredApiKey = (
  savedConfig: ProviderConfig | undefined,
  selectedProvider: string,
): boolean =>
  Boolean(
    selectedProvider &&
    savedConfig?.provider === selectedProvider &&
    savedConfig.config?.api_key_set === true,
  );

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
  baseUrl,
}: {
  provider: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
}) => {
  if (!provider) {
    return undefined;
  }

  return {
    provider,
    config: {
      model: model || undefined,
      api_key:
        apiKey?.trim() && apiKey.trim() !== "[redacted]"
          ? apiKey.trim()
          : undefined,
      // `openai_base_url` is understood only by OpenAI-compatible providers.
      // Omitting it for other providers avoids passing an incompatible option
      // when an administrator switches providers in the same form.
      openai_base_url:
        provider === "openai" ? baseUrl?.trim() || undefined : undefined,
    },
  };
};
