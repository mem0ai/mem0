import { withoutTrailingSlash } from '@ai-sdk/provider-utils'

import { Mem0GenericLanguageModel } from './mem0-generic-language-model'
import { Mem0ChatModelId, Mem0ChatSettings } from './mem0-types'
import { Mem0ProviderSettings } from './mem0-provider'

export class Mem0 {
  readonly baseURL: string
  readonly headers?: any

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
      headers: this.headers,
    }
  }

  chat(modelId: Mem0ChatModelId, settings: Mem0ChatSettings = {}) {
    return new Mem0GenericLanguageModel(modelId, settings, {
      provider: 'openai',
      modelType: 'chat',
      ...this.baseConfig,
    })
  }

  completion(modelId: Mem0ChatModelId, settings: Mem0ChatSettings = {}) {
    return new Mem0GenericLanguageModel(modelId, settings, {
      provider: 'openai',
      modelType: 'completion',
      ...this.baseConfig,
    })
  }
}