import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

export class LiteLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    super({
      ...config,
      apiKey: config.apiKey || process.env.LITELLM_API_KEY || "sk-anything",
      baseURL:
        config.baseURL ||
        process.env.LITELLM_API_BASE ||
        "http://localhost:4000",
      model: config.model || "gpt-5-mini",
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
      throw new Error(`LiteLLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`LiteLLM failed: ${message}`);
    }
  }
}
