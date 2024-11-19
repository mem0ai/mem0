/* eslint-disable camelcase */
import {
  LanguageModelV1,
  LanguageModelV1CallOptions,
  LanguageModelV1CallWarning,
  LanguageModelV1FinishReason,
  LanguageModelV1FunctionToolCall,
  LanguageModelV1LogProbs,
  LanguageModelV1ProviderMetadata,
  LanguageModelV1StreamPart,
} from "@ai-sdk/provider";

import { Mem0ChatModelId, Mem0ChatSettings } from "./mem0-chat-settings";
import { Mem0ClassSelector } from "./mem0-provider-selector";
import { filterStream } from "./stream-utils";
import { Mem0Config } from "./mem0-chat-settings";
import { OpenAIProviderSettings } from "@ai-sdk/openai";
import { Mem0ProviderSettings } from "./mem0-provider";


interface Mem0ChatConfig {
  baseURL: string;
  fetch?: typeof fetch;
  headers: () => Record<string, string | undefined>;
  provider: string;
  organization?: string;
  project?: string;
  name?: string;
  apiKey?: string;
  mem0_api_key?: string;
}

export class Mem0GenericLanguageModel implements LanguageModelV1 {
  readonly specificationVersion = "v1";
  readonly defaultObjectGenerationMode = "json";
  readonly supportsImageUrls = false;

  constructor(
    public readonly modelId: Mem0ChatModelId,
    public readonly settings: Mem0ChatSettings,
    public readonly config: Mem0ChatConfig,
    public readonly provider_config?: OpenAIProviderSettings
  ) {
    this.provider = config.provider;
  }

  provider: string;
  supportsStructuredOutputs?: boolean | undefined;

  async doGenerate(options: LanguageModelV1CallOptions): Promise<{
    text?: string;
    toolCalls?: Array<LanguageModelV1FunctionToolCall>;
    finishReason: LanguageModelV1FinishReason;
    usage: { promptTokens: number; completionTokens: number };
    rawCall: { rawPrompt: unknown; rawSettings: Record<string, unknown> };
    rawResponse?: { headers?: Record<string, string> };
    response?: { id?: string; timestamp?: Date; modelId?: string };
    warnings?: LanguageModelV1CallWarning[];
    providerMetadata?: LanguageModelV1ProviderMetadata;
    logprobs?: LanguageModelV1LogProbs;
  }> {
    try {
      const provider = this.config.provider;
      const mem0_api_key = this.config.mem0_api_key;
      const settings: Mem0ProviderSettings = {
        provider: provider,
        mem0ApiKey: mem0_api_key,
        apiKey: this.config.apiKey,
      }
      const selector = new Mem0ClassSelector(this.modelId, settings,this.provider_config);
      let messagesPrompts = options.prompt;
      const model = selector.createProvider();
      const user_id = this.settings.user_id;
      const app_id = this.settings.app_id;
      const agent_id = this.settings.agent_id;
      const run_id = this.settings.run_id;
      const org_name = this.settings.org_name;
      const project_name = this.settings.project_name;
      const apiKey = mem0_api_key;

      const config: Mem0Config = {user_id, app_id, agent_id, run_id, org_name, project_name, mem0ApiKey: apiKey};

      const ans = await model.generateText(messagesPrompts, config);
 

      return {
        text: ans.text,
        finishReason: ans.finishReason,
        usage: ans.usage,
        rawCall: {
          rawPrompt: options.prompt,
          rawSettings: {},
        },
        response: ans.response,
        warnings: ans.warnings,
      };
    } catch (error) {
      // Handle errors properly
      console.error("Error in doGenerate:", error);
      throw new Error("Failed to generate response.");
    }
  }

  async doStream(options: LanguageModelV1CallOptions): Promise<{
    stream: ReadableStream<LanguageModelV1StreamPart>;
    rawCall: { rawPrompt: unknown; rawSettings: Record<string, unknown> };
    rawResponse?: { headers?: Record<string, string> };
    warnings?: LanguageModelV1CallWarning[];
  }> {
    try {
      const provider = this.config.provider;
      const mem0_api_key = this.config.mem0_api_key;
      const settings: Mem0ProviderSettings = {
        provider: provider,
        mem0ApiKey: mem0_api_key,
        apiKey: this.config.apiKey,
      }
      const selector = new Mem0ClassSelector(this.modelId, settings,this.provider_config);
      let messagesPrompts = options.prompt;
      const model = selector.createProvider();
      const user_id = this.settings.user_id;
      const app_id = this.settings.app_id;
      const agent_id = this.settings.agent_id;
      const run_id = this.settings.run_id;
      const org_name = this.settings.org_name;
      const project_name = this.settings.project_name;

      const apiKey = mem0_api_key;

      const config: Mem0Config = {user_id, app_id, agent_id, run_id, org_name, project_name, mem0ApiKey: apiKey};
      const response = await model.streamText(messagesPrompts, config);
      // @ts-ignore
      const filteredStream = await filterStream(response.originalStream);
      return {
        // @ts-ignore
        stream: filteredStream,
        rawCall: {
          rawPrompt: options.prompt,
          rawSettings: {},
        },
        ...response,
      };
    } catch (error) {
      console.error("Error in doStream:", error);
      throw new Error("Streaming failed or method not implemented.");
    }
  }
}
