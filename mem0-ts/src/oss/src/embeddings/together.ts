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
      baseURL: config.baseURL || config.url || DEFAULT_BASE_URL,
      model: config.model || DEFAULT_MODEL,
    });
  }
}
