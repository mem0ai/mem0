import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class OpenAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;
  private embeddingDims: number;
  private passDimensionsToApi: boolean;

  constructor(config: EmbeddingConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseURL || config.url,
    });
    this.model = config.model || "text-embedding-3-small";
    // Only pass `dimensions` when the user explicitly set embeddingDims;
    // some OpenAI-compatible backends (vLLM, Voyage, etc.) reject the parameter.
    this.passDimensionsToApi = config.embeddingDims != null;
    this.embeddingDims = config.embeddingDims || 1536;
  }

  async embed(text: string): Promise<number[]> {
    const params: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: this.model,
      input: text,
    };
    if (this.passDimensionsToApi) {
      params.dimensions = this.embeddingDims;
    }
    const response = await this.openai.embeddings.create(params);
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const params: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: this.model,
      input: texts,
    };
    if (this.passDimensionsToApi) {
      params.dimensions = this.embeddingDims;
    }
    const response = await this.openai.embeddings.create(params);
    return response.data.map((item) => item.embedding);
  }
}
