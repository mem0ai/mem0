import { LanguageModelV1, ProviderV1 } from '@ai-sdk/provider'
import { withoutTrailingSlash } from '@ai-sdk/provider-utils'

import { Mem0ChatLanguageModel } from './mem0-chat-language-model'
import { Mem0ChatModelId, Mem0ChatSettings } from './mem0-chat-settings'
import { OpenAIProviderSettings } from '@ai-sdk/openai'
import { Mem0CompletionModelId, Mem0CompletionSettings } from './mem0-completion-settings'
import { Mem0GenericLanguageModel } from './mem0-generic-language-model'
import { Mem0CompletionLanguageModel } from './mem0-completion-language-model'


export interface Mem0Provider extends ProviderV1 {
  (modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV1

  chat(
    modelId: Mem0ChatModelId,
    settings?: Mem0ChatSettings,
  ): LanguageModelV1


  languageModel(
    modelId: Mem0ChatModelId,
    settings?: Mem0ChatSettings,
  ): LanguageModelV1

  completion(
    modelId: Mem0CompletionModelId,
    settings?: Mem0CompletionSettings,
  ): LanguageModelV1
}

export interface Mem0ProviderSettings extends OpenAIProviderSettings {
  baseURL?: string
  /**
   * Custom fetch implementation. You can use it as a middleware to intercept
   * requests or to provide a custom fetch implementation for e.g. testing
   */
  fetch?: typeof fetch
  /**
   * @internal
   */
  generateId?: () => string
  /**
   * Custom headers to include in the requests.
   */
  headers?: Record<string, string>
  organization?: string;
  project?: string;
  name?: string;
  mem0ApiKey?: string;
  apiKey?: string;
  provider?: string;
  config?: OpenAIProviderSettings;
  modelType?: "completion" | "chat";
}

export function createMem0(
  options: Mem0ProviderSettings = {
    provider: "openai",
  },
): Mem0Provider {
  const baseURL =
    withoutTrailingSlash(options.baseURL) ?? 'http://127.0.0.1:11434/api'

  const getHeaders = () => ({
    ...options.headers,
  })

  const createGenericModel = (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {},
  ) =>
    new Mem0GenericLanguageModel(modelId, settings, {
      baseURL,
      fetch: options.fetch,
      headers: getHeaders,
      provider: options.provider || "openai",
      organization: options.organization,
      project: options.project,
      name: options.name,
      mem0_api_key: options.mem0ApiKey,
      apiKey: options.apiKey,
    }, options.config)

  const createChatModel = (
    modelId: Mem0ChatModelId,
    settings: Mem0ChatSettings = {},
  ) =>
    
    new Mem0ChatLanguageModel(modelId, settings, {
      baseURL,
      fetch: options.fetch,
      headers: getHeaders,
      provider: options.provider || "openai",
      organization: options.organization,
      project: options.project,
      name: options.name,
      mem0_api_key: options.mem0ApiKey,
      apiKey: options.apiKey,
    }, options.config)

    const createCompletionModel = (
      modelId: Mem0CompletionModelId,
      settings: Mem0CompletionSettings = {}
    ) =>
      new Mem0CompletionLanguageModel(
        modelId,
        settings,
        {
          baseURL,
          fetch: options.fetch,
          headers: getHeaders,
          provider: options.provider || "openai",
          organization: options.organization,
          project: options.project,
          name: options.name,
          mem0_api_key: options.mem0ApiKey,
          apiKey: options.apiKey
        },
        options.config
      );

  const provider = function (
    modelId: Mem0ChatModelId,
    settings?: Mem0ChatSettings,
  ) {
    if (new.target) {
      throw new Error(
        'The Mem0 model function cannot be called with the new keyword.',
      )
    }

    return createGenericModel(modelId, settings)
  }
    


  provider.chat = createChatModel
  provider.completion = createCompletionModel
  provider.languageModel = createChatModel

  return provider as unknown as Mem0Provider
}

export const mem0 = createMem0()