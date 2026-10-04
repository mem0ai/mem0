import { OpenAIEmbedder } from "./openai";
import { EmbeddingConfig } from "../types";

const DEFAULT_BASE_URL = "https://api.together.ai/v1";
const DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct";

export class TogetherEmbedder extends OpenAIEmbedder {
  constructor(config: EmbeddingConfig) {
    const openAICompatibleConfig = { ...config };
    delete openAICompatibleConfig.embeddingDims;

    const apiKey = config.apiKey || process.env.TOGETHER_API_KEY;
    if (!apiKey) {
      throw new Error("Together API key is required");
    }

    super({
      ...openAICompatibleConfig,
      apiKey,
      // Honor TOGETHER_API_BASE like the Together LLM does, so a user behind a
      // gateway who sets it gets it for embeddings too instead of silently
      // hitting api.together.ai.
      baseURL:
        config.baseURL ||
        config.url ||
        process.env.TOGETHER_API_BASE ||
        DEFAULT_BASE_URL,
      model: config.model || DEFAULT_MODEL,
    });
  }
}
