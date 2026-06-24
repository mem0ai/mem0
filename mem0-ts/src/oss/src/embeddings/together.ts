import { OpenAIEmbedder } from "./openai";
import { EmbeddingConfig } from "../types";

export class TogetherEmbedder extends OpenAIEmbedder {
  constructor(config: EmbeddingConfig) {
    super({
      ...config,
      baseURL: config.baseURL || "https://api.together.xyz/v1",
      model: config.model || "sentence-transformers__all-minilm-l6-v2",
    });
  }
}
