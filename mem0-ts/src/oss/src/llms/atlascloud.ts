import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

export class AtlasCloudLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ATLASCLOUD_API_KEY;
    if (!apiKey) {
      throw new Error("Atlas Cloud API key is required");
    }
    super({
      ...config,
      apiKey,
      baseURL:
        config.baseURL ||
        process.env.ATLASCLOUD_API_BASE ||
        "https://api.atlascloud.ai/v1",
      model: config.model || "deepseek-ai/DeepSeek-V3.1-Terminus",
    });
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    try {
      return await super.generateResponse(messages, responseFormat, tools);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`Atlas Cloud LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`Atlas Cloud LLM failed: ${message}`);
    }
  }
}
