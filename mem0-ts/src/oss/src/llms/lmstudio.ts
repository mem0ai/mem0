import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

const DEFAULT_BASE_URL = "http://localhost:1234/v1";
const DEFAULT_MODEL =
  "lmstudio-community/Meta-Llama-3.1-70B-Instruct-GGUF/Meta-Llama-3.1-70B-Instruct-IQ2_M.gguf";
const DEFAULT_LMSTUDIO_API_KEY = "lm-studio";

export class LMStudioLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    // config > LMSTUDIO_BASE_URL env > localhost default (mirror deepseek.ts / Python LMStudioLLM)
    const baseURL =
      config.baseURL || process.env.LMSTUDIO_BASE_URL || DEFAULT_BASE_URL;
    super({
      ...config,
      apiKey: config.apiKey || DEFAULT_LMSTUDIO_API_KEY,
      baseURL,
      model: config.model || DEFAULT_MODEL,
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
      throw new Error(`LM Studio LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`LM Studio LLM failed: ${message}`);
    }
  }
}
