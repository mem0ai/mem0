import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

export class SarvamLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.SARVAM_API_KEY;
    if (!apiKey) {
      throw new Error("Sarvam API key is required");
    }
    super({
      ...config,
      apiKey,
      baseURL:
        config.baseURL ||
        process.env.SARVAM_API_BASE ||
        "https://api.sarvam.ai",
      model: config.model || "sarvam-m",
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
      throw new Error(`Sarvam LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`Sarvam LLM failed: ${message}`);
    }
  }
}
