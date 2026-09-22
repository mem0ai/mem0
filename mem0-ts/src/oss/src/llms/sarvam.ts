import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

/**
 * Sarvam AI LLM provider.
 *
 * Sarvam's API is OpenAI-compatible, so this simply reuses {@link OpenAILLM}
 * and overrides the connection defaults — mirroring `mem0/llms/sarvam.py` in the
 * Python SDK. The API key resolves from `config.apiKey` or the `SARVAM_API_KEY`
 * env var, and the base URL from `config.baseURL`, `SARVAM_API_BASE`, else
 * `https://api.sarvam.ai/v1`.
 */
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
        "https://api.sarvam.ai/v1",
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
