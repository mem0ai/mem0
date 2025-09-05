import Together from "together-ai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class TogetherEmbedder implements Embedder {
  private together: Together;
  private model: string;

  constructor(config: EmbeddingConfig) {
    if (!config.apiKey) {
      throw new Error("Together AI requires an API key");
    }

    this.together = new Together({
      apiKey: config.apiKey,
    });
    this.model = config.model || "togethercomputer/m2-bert-80M-8k-retrieval";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.together.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.together.embeddings.create({
      model: this.model,
      input: texts,
    });
    return response.data.map((item: any) => item.embedding);
  }
} 