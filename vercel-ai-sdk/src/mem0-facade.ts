import { withoutTrailingSlash } from '@ai-sdk/provider-utils'

import { Mem0ChatLanguageModel } from './mem0-chat-language-model'
import { Mem0ChatModelId, Mem0ChatSettings } from './mem0-chat-settings'
import { Mem0ProviderSettings } from './mem0-provider'

export class Mem0 {
  readonly baseURL: string

  readonly headers?: Record<string, string>

  constructor(options: Mem0ProviderSettings = {
    provider: 'openai',
  }) {
    this.baseURL =
      withoutTrailingSlash(options.baseURL) ?? 'http://127.0.0.1:11434/api'

    this.headers = options.headers
  }

  private get baseConfig() {
    return {
      baseURL: this.baseURL,
      headers: () => ({
        ...this.headers,
      }),
    }
  }

  chat(modelId: Mem0ChatModelId, settings: Mem0ChatSettings = {}) {
    return new Mem0ChatLanguageModel(modelId, settings, {
      provider: 'openai',
      ...this.baseConfig,
    })
  }
}