import { ProviderV2 } from '@ai-sdk/provider';
import { LanguageModelV2 } from '@ai-sdk/provider';
import { withoutTrailingSlash } from "@ai-sdk/provider-utils";
import { Mem0ChatModelId, Mem0ChatSettings, Mem0Config } from "./mem0-types";
import { Mem0GenericLanguageModel } from "./mem0-generic-language-model";
import { LLMProviderSettings } from "./mem0-types";

export interface Mem0Provider extends ProviderV2 {
  (modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;

  chat(modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;
  completion(modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;

  languageModel(
    modelId: Mem0ChatModelId,
    settings?: Mem0ChatSettings
  ): LanguageModelV2;
}

export interface Mem0ProviderSettings {
  baseURL?: string;
  /**
   * Custom fetch implementation. You can use it as a middleware to intercept
   * requests or to provide a custom fetch implementation for e.g. testing
   */
  fetch?: typeof fetch;
  /**
   * @internal
   */
  generateId?: () => string;
  /**
   * Custom headers to include in the requests.
   */
  headers?: Record<string, string>;
  name?: string;
  mem0ApiKey?: string;
  apiKey?: string;
  provider?: string;
  modelType?: "completion" | "chat";
  mem0Config?: Mem0Config;

  /**
   * The configuration for the provider.
   */
  config?: LLMProviderSettings ;
}

export function createMem0(
  options: Mem0ProviderSettings = {
    provider: "openai",
  }
): Mem0Provider {
  const baseURL =
    withoutTrailingSlash(options.baseURL) ?? "http://api.openai.com";
  const getHeaders = () => ({
    ...options.headers,
  });

  const createGenericModel = (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {}
  ) =>
    new Mem0GenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        mem0ApiKey: options.mem0ApiKey,
        apiKey: options.apiKey,
        mem0Config: options.mem0Config,
      },
      options.config
    );

  const createCompletionModel = (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {}
  ) =>
    new Mem0GenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        mem0ApiKey: options.mem0ApiKey,
        apiKey: options.apiKey,
        mem0Config: options.mem0Config,
        modelType: "completion",
      },
      options.config
    );

  const createChatModel = (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {}
  ) =>
    new Mem0GenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        mem0ApiKey: options.mem0ApiKey,
        apiKey: options.apiKey,
        mem0Config: options.mem0Config,
        modelType: "completion",
      },
      options.config
    );

  const provider = function (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {}
  ) {
    if (new.target) {
      throw new Error(
        "The Mem0 model function cannot be called with the new keyword."
      );
    }

    return createGenericModel(modelId, settings);
  };

  provider.languageModel = createGenericModel;
  provider.completion = createCompletionModel;
  provider.chat = createChatModel;

  return provider as unknown as Mem0Provider;
}

export const mem0 = createMem0();
