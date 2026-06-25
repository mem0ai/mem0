import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

export class TogetherLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.TOGETHER_API_KEY;
    if (!apiKey) {
      throw new Error("Together API key is required");
    }
    super({
      ...config,
      apiKey,
      baseURL:
        config.baseURL ||
        process.env.TOGETHER_API_BASE ||
        "https://api.together.xyz/v1",
      model: config.model || "mistralai/Mixtral-8x7B-Instruct-v0.1",
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
      throw new Error(`Together LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`Together LLM failed: ${message}`);
    }
  }
}
