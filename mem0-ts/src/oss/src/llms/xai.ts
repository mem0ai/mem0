import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

/**
 * xAI (Grok) LLM provider.
 *
 * xAI's Grok API is OpenAI-compatible, so this simply reuses {@link OpenAILLM}
 * and overrides the connection defaults — mirroring `mem0/llms/xai.py` in the
 * Python SDK. The API key resolves from `config.apiKey` or the `XAI_API_KEY`
 * env var, and the base URL from `config.baseURL`, `XAI_API_BASE`, else
 * `https://api.x.ai/v1`.
 */
export class XAILLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.XAI_API_KEY;
    if (!apiKey) {
      throw new Error("xAI API key is required");
    }
    super({
      ...config,
      apiKey,
      baseURL:
        config.baseURL || process.env.XAI_API_BASE || "https://api.x.ai/v1",
      model: config.model || "grok-4.3",
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
      throw new Error(`xAI LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`xAI LLM failed: ${message}`);
    }
  }
}
