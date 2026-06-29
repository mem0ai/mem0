import { OpenAIEmbedder } from "./openai";
import { TogetherEmbeddingConfig } from "../types";

const DEFAULT_BASE_URL = "https://api.together.xyz/v1";
const DEFAULT_MODEL = "togethercomputer/m2-bert-80M-8k-retrieval";

export class TogetherEmbedder extends OpenAIEmbedder {
  constructor(config: TogetherEmbeddingConfig) {
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
