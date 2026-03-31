import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class OpenAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;
  private embeddingDims?: number;
  private passDimensionsToApi: boolean;

  constructor(config: EmbeddingConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseURL || config.url,
    });
    this.model = config.model || "text-embedding-3-small";
    this.passDimensionsToApi = config.embeddingDims != null;
    this.embeddingDims = config.embeddingDims ?? 1536;
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
      ...(this.passDimensionsToApi && { dimensions: this.embeddingDims }),
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: texts,
      ...(this.passDimensionsToApi && { dimensions: this.embeddingDims }),
    });
    return response.data.map((item) => item.embedding);
  }
}
