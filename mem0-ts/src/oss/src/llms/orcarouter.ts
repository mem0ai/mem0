import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

/**
 * OrcaRouter provider - https://www.orcarouter.ai/
 *
 * OrcaRouter is an OpenAI-compatible API gateway that routes requests across multiple LLM providers
 * (OpenAI, Anthropic, DeepSeek, etc.) with a variety of intelligent routing strategies.
 *
 * Documentation: https://docs.orcarouter.ai/introduction
 */
export class OrcaRouterLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ORCAROUTER_API_KEY;
    if (!apiKey) {
      throw new Error("OrcaRouter API key is required");
    }
    super({
      ...config,
      apiKey,
      baseURL:
        config.baseURL ||
        process.env.ORCAROUTER_API_BASE ||
        "https://api.orcarouter.ai/v1",
      model: config.model || "orcarouter/auto",
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
      throw new Error(`OrcaRouter LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`OrcaRouter LLM failed: ${message}`);
    }
  }
}
