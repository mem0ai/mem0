import { OpenAILLM } from "./openai";
import { LLMConfig, Message } from "../types";
import { LLMResponse } from "./base";

const DEFAULT_MODEL = "Qwen/Qwen2.5-32B-Instruct";
const DEFAULT_API_KEY = "vllm-api-key";
// Mirrors the Python provider default (mem0/configs/llms/vllm.py) and the docs table.
const DEFAULT_BASE_URL = "http://localhost:8000/v1";

export class VllmLLM extends OpenAILLM {
  constructor(config: LLMConfig) {
    const baseURL =
      config.baseURL ||
      config.vllmBaseURL ||
      config.vllm_base_url ||
      config.url ||
      process.env.VLLM_BASE_URL ||
      DEFAULT_BASE_URL;

    super({
      ...config,
      apiKey: config.apiKey || process.env.VLLM_API_KEY || DEFAULT_API_KEY,
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
      throw new Error(`vLLM LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      return await super.generateChat(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`vLLM LLM failed: ${message}`);
    }
  }
}
